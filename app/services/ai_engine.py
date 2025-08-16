"""
최적화된 AI 엔진 (OpenAI API)
"""
import json
import asyncio
from time import monotonic
from typing import Dict, Any

from openai import AsyncOpenAI

from ..models.schemas import ExtractedFacts, UserProfile, FACTS_SCHEMA, REWRITE_SCHEMA
from ..core.config import settings
from ..core.logging import get_logger
from ..utils.helpers import with_retry, coerce_json
from ..utils.cache import cache_manager

logger = get_logger("ai_engine")


class AIEngine:
    """최적화된 AI 기반 콘텐츠 처리 엔진"""
    
    def __init__(self, api_key: str):
        if not api_key or api_key == "test-key":
            raise RuntimeError("OPENAI_API_KEY가 설정되어 있지 않습니다.")
        
        self.client = AsyncOpenAI(
            api_key=api_key,
            timeout=float(settings.openai_timeout),
            max_retries=0  # 우리 쪽 with_retry만 사용
        )
        self.model = settings.openai_model
        self._structured_outputs_tested = False
        self._supports_structured = None
        
        # 2025년 최적화: 동적 세마포어 조정
        self._concurrent_limit = asyncio.Semaphore(settings.openai_concurrency_limit)
        
        # 레이트 리미터
        from ..utils.helpers import RateLimiter
        self._rate_limiter = RateLimiter(
            max_calls=settings.rate_limit_per_minute,
            time_window=60
        )
    
    async def _call_with_schema(self, messages: list, schema: dict, 
                               temperature: float = 0.1, max_tokens: int = 800):
        """Structured Outputs 호출 (런타임 폴백 지원)"""
        
        # 첫 호출에서만 지원 여부 테스트
        if settings.use_structured_outputs and not self._structured_outputs_tested:
            self._structured_outputs_tested = True
            try:
                async with self._concurrent_limit:
                    test_response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": "test"}],
                        temperature=0,
                        max_tokens=10,
                        timeout=10.0,
                        response_format={
                            "type": "json_schema",
                            "json_schema": {
                                "name": "test",
                                "schema": {
                                    "type": "object", 
                                    "properties": {"test": {"type": "string"}}, 
                                    "required": ["test"]
                                },
                                "strict": True
                            }
                        }
                    )
                self._supports_structured = True
                logger.info("Structured Outputs 지원 확인됨", model=self.model)
            except Exception as e:
                self._supports_structured = False
                logger.info("Structured Outputs 미지원, JSON 모드 사용", 
                           model=self.model, error=str(e)[:100])
        
        # 레이트 리미팅 적용
        await self._rate_limiter.acquire()
        
        # 실제 호출
        async with self._concurrent_limit:
            start = monotonic()
            
            try:
                if settings.use_structured_outputs and self._supports_structured:
                    response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        timeout=float(settings.openai_timeout),
                        response_format={
                            "type": "json_schema",
                            "json_schema": {
                                "name": schema.get("name", "Response"),
                                "schema": schema.get("schema", schema),
                                "strict": True
                            }
                        }
                    )
                else:
                    # JSON 모드 사용 (폴백 또는 기본)
                    response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        timeout=float(settings.openai_timeout),
                        response_format={"type": "json_object"}
                    )
                
                # 응답 메트릭 로깅
                latency_ms = int((monotonic() - start) * 1000)
                finish_reason = getattr(response.choices[0], "finish_reason", None)
                usage = getattr(response, "usage", None)
                
                logger.debug("OpenAI API 호출 완료",
                           mode="structured" if (settings.use_structured_outputs and self._supports_structured) else "json",
                           finish_reason=finish_reason,
                           latency_ms=latency_ms,
                           prompt_tokens=getattr(usage, "prompt_tokens", None),
                           completion_tokens=getattr(usage, "completion_tokens", None),
                           total_tokens=getattr(usage, "total_tokens", None))
                
                # Prometheus 토큰 메트릭 기록 (2025년 모니터링 표준)
                try:
                    # 전역에서 OPENAI_TOKENS 메트릭 사용 (backend.txt에서 정의)
                    import sys
                    if 'OPENAI_TOKENS' in dir(sys.modules.get('__main__', {})):
                        main_module = sys.modules['__main__']
                        if hasattr(main_module, 'OPENAI_TOKENS') and usage:
                            if getattr(usage, "prompt_tokens", None) is not None:
                                main_module.OPENAI_TOKENS.labels("prompt", self.model).inc(usage.prompt_tokens)
                            if getattr(usage, "completion_tokens", None) is not None:
                                main_module.OPENAI_TOKENS.labels("completion", self.model).inc(usage.completion_tokens)
                except Exception:
                    pass  # 메트릭 실패는 조용히 무시
                
                if finish_reason == "length":
                    logger.warning("응답이 max_tokens에 도달했습니다")
                elif finish_reason == "content_filter":
                    logger.warning("콘텐츠 필터로 응답이 차단되었습니다")
                
                return response
                
            except Exception as e:
                if "schema" in str(e).lower() and self._supports_structured:
                    logger.warning("Structured Outputs 실패, JSON 모드로 폴백", error=str(e)[:100])
                    self._supports_structured = False
                    # 재귀 호출로 JSON 모드 시도
                    return await self._call_with_schema(messages, schema, temperature, max_tokens)
                raise
    
    @cache_manager.cache_result(ttl=3600, key_prefix="facts:")
    async def extract_facts(self, article: Dict[str, Any]) -> ExtractedFacts:
        """팩트 추출 (캐시 적용)"""
        system = "너는 팩트 추출기다. 반드시 JSON만 출력한다. 의견/추측/전망은 제외하라."
        user = f"""
기사 제목: {article['title']}
기사 내용: {article['content']}

이 JSON 스키마로만 응답:
{{
  "who": ["string"],
  "what": "string",
  "when": "string",
  "where": "string",
  "why": "string",
  "how": "string",
  "numbers": {{"항목":"수치"}},
  "quotes": [{{"speaker":"string","content":"string"}}],
  "verified_facts": ["string"]
}}
"""
        
        async def _call():
            return await self._call_with_schema(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                schema={"name": "ExtractedFacts", "schema": FACTS_SCHEMA},
                temperature=0.1,
                max_tokens=800
            )
        
        try:
            response = await with_retry(_call, retries=settings.openai_retries, base_delay=1.0)
            
            if not getattr(response, "choices", None) or not response.choices:
                logger.error("OpenAI 응답이 비어있음", model=self.model, op="extract_facts")
                raise RuntimeError("Empty OpenAI choices")
            
            raw_content = getattr(response.choices[0].message, "content", None) or "{}"
            try:
                data = json.loads(raw_content)
            except json.JSONDecodeError:
                logger.warning("JSON 파싱 실패, 복구 시도", content_preview=raw_content[:100])
                data = coerce_json(raw_content)
            
            return ExtractedFacts(
                who=(data.get("who", []) or [])[:10],
                what=(data.get("what", "") or "")[:200],
                when=(data.get("when", "") or "")[:100],
                where=(data.get("where", "") or "")[:100],
                why=(data.get("why", "") or "")[:200],
                how=(data.get("how", "") or "")[:200],
                numbers=data.get("numbers", {}) or {},
                quotes=(data.get("quotes", []) or [])[:5],
                verified_facts=(data.get("verified_facts", []) or [])[:10]
            )
            
        except Exception as e:
            logger.error("팩트 추출 실패", error=str(e), article_id=article.get('id'))
            # fallback 데이터 반환
            return ExtractedFacts(
                who=[],
                what=article.get('title', '')[:200],
                when="",
                where="",
                why="",
                how="",
                numbers={},
                quotes=[],
                verified_facts=[]
            )
    
    async def rewrite_for_user(self, facts: ExtractedFacts, profile: UserProfile) -> Dict[str, Any]:
        """사용자 맞춤 재작성"""
        mode_guides = {
            "quick": {"sentences": [3, 5], "time": "30초", "style": "핵심만 간결하게"},
            "standard": {"sentences": [10, 15], "time": "1-2분", "style": "적절한 배경 설명"},
            "deep": {"sentences": [20, 30], "time": "3-5분", "style": "상세 분석"}
        }
        guide = mode_guides[profile.reading_mode]
        
        # 관심사 통합
        all_interests = (
            profile.interests_finance + profile.interests_lifestyle +
            profile.interests_hobby + profile.interests_tech
        )[:10]  # MAX_INTERESTS
        
        primary_job = profile.job_categories[0] if profile.job_categories else "일반"
        primary_interest = all_interests[0] if all_interests else "일반"
        
        # 수치 정보 포함 지시
        numbers_instruction = ""
        if facts.numbers:
            numbers_instruction = f"\n- 첫 단락에 다음 수치 중 하나를 반드시 포함: {list(facts.numbers.values())[:3]}"
        
        system = "너는 뉴스 재작성기다. 반드시 JSON만 출력한다. 한국어로 작성한다."
        user = f"""
팩트 데이터:
- who: {', '.join(facts.who[:5])}
- what: {facts.what}
- when: {facts.when}
- where: {facts.where}
- why: {facts.why}
- how: {facts.how}
- numbers: {json.dumps(facts.numbers, ensure_ascii=False)}

독자 프로필:
- {profile.age}세 {profile.gender}
- 직업: {', '.join(profile.job_categories[:3])}
- 관심사: {', '.join(all_interests[:5])}
- 상황: {profile.work_style}, {profile.family_status}

작성 요구사항:
- 문장 수: {guide['sentences'][0]}-{guide['sentences'][1]}
- 읽기 시간: {guide['time']}
- 톤: {guide['style']}
- {primary_job} 업무 관점 포함
- {primary_interest} 관련성 언급{numbers_instruction}

JSON 형식:
{{
  "title": "매력적인 헤드라인",
  "content": "본문 내용",
  "key_points": ["핵심1", "핵심2", "핵심3"],
  "reading_time": "{guide['time']}"
}}
"""
        
        async def _call():
            return await self._call_with_schema(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                schema={"name": "PersonalizedArticle", "schema": REWRITE_SCHEMA},
                temperature=0.6,
                max_tokens=1000
            )
        
        try:
            response = await with_retry(_call, retries=settings.openai_retries, base_delay=1.0)
            
            if not getattr(response, "choices", None) or not response.choices:
                logger.error("OpenAI 응답이 비어있음", model=self.model, op="rewrite_for_user")
                return self._create_fallback_content(facts, guide)
            
            raw_content = getattr(response.choices[0].message, "content", None) or "{}"
            try:
                obj = json.loads(raw_content)
            except json.JSONDecodeError:
                logger.warning("JSON 파싱 실패, 복구 시도", content_preview=raw_content[:100])
                obj = coerce_json(raw_content)
            
            return {
                "title": (obj.get("title") or facts.what or "뉴스")[:200],
                "content": (obj.get("content") or "")[:2000],
                "key_points": [p[:100] for p in (obj.get("key_points") or [])[:3]],
                "reading_time": obj.get("reading_time") or guide["time"]
            }
            
        except Exception as e:
            logger.error("재작성 실패", error=str(e), user_id=profile.user_id[:10])
            return self._create_fallback_content(facts, guide)
    
    def _create_fallback_content(self, facts: ExtractedFacts, guide: Dict[str, Any]) -> Dict[str, Any]:
        """재작성 실패 시 fallback 콘텐츠 생성"""
        return {
            "title": facts.what or "뉴스",
            "content": f"{facts.what}. {facts.when}에 발생한 사건입니다.",
            "key_points": facts.verified_facts[:3] or ["정보 처리 중입니다"],
            "reading_time": guide["time"]
        }
    
    async def health_check(self) -> bool:
        """AI 엔진 상태 확인"""
        try:
            async with self._concurrent_limit:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": "ping"}],
                    temperature=0,
                    max_tokens=5,
                    timeout=10.0
                )
                return bool(response.choices)
        except Exception as e:
            logger.error("AI 엔진 헬스체크 실패", error=str(e))
            return False