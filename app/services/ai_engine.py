"""
최적화된 AI 엔진 (OpenAI API)
"""
import json
import asyncio
from time import monotonic
from typing import Dict, Any

from openai import AsyncOpenAI
from groq import AsyncGroq

from ..models.schemas import ExtractedFacts, UserProfile, FACTS_SCHEMA, REWRITE_SCHEMA
from ..core.config import settings
from ..core.logging import get_logger
from ..utils.helpers import with_retry, coerce_json
# from ..utils.cache import cache_manager  # 캐시 완전 제거

logger = get_logger("ai_engine")


class AIEngine:
    """최적화된 AI 기반 콘텐츠 처리 엔진"""
    
    def __init__(self, api_key: str):
        if settings.ai_provider == "groq":
            if not settings.groq_api_key:
                raise RuntimeError("GROQ_API_KEY가 설정되어 있지 않습니다.")
            self.client = AsyncGroq(api_key=settings.groq_api_key)
            self.model = settings.groq_model
            self.provider = "groq"
        elif settings.ai_provider == "dual":
            # Dual 모드: Groq와 OpenAI 둘 다 초기화
            if not settings.groq_api_key or not api_key:
                raise RuntimeError("Dual 모드에서는 GROQ_API_KEY와 OPENAI_API_KEY가 모두 필요합니다.")
            self.groq_client = AsyncGroq(api_key=settings.groq_api_key)
            self.openai_client = AsyncOpenAI(api_key=api_key, timeout=float(settings.openai_timeout), max_retries=0)
            self.client = self.groq_client  # 기본은 Groq
            self.model = settings.groq_model
            self.provider = "dual"
        else:
            if not api_key or api_key == "test-key":
                raise RuntimeError("OPENAI_API_KEY가 설정되어 있지 않습니다.")
            self.client = AsyncOpenAI(
                api_key=api_key,
                timeout=float(settings.openai_timeout),
                max_retries=0
            )
            self.model = settings.openai_model
            self.provider = "openai"
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
                               temperature: float = 0.1, max_tokens: int = 8000):
        """AI API 호출 (OpenAI/Groq 지원)"""
        
        start = monotonic()
        
        try:
            if self.provider == "groq":
                # Groq API 호출 (JSON 모드)
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"}
                )
                
                logger.debug("Groq API 호출 완료",
                           model=self.model,
                           latency_ms=int((monotonic() - start) * 1000),
                           prompt_tokens=getattr(response.usage, "prompt_tokens", None),
                           completion_tokens=getattr(response.usage, "completion_tokens", None),
                           total_tokens=getattr(response.usage, "total_tokens", None))
                
            else:
                # OpenAI API 호출 (기존 로직)
                if not self._structured_outputs_tested:
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
                
                async with self._concurrent_limit:
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
                        response = await self.client.chat.completions.create(
                            model=self.model,
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            timeout=float(settings.openai_timeout),
                            response_format={"type": "json_object"}
                        )
                    
                    logger.debug("OpenAI API 호출 완료",
                               mode="structured" if (settings.use_structured_outputs and self._supports_structured) else "json",
                               latency_ms=int((monotonic() - start) * 1000),
                               prompt_tokens=getattr(response.usage, "prompt_tokens", None),
                               completion_tokens=getattr(response.usage, "completion_tokens", None),
                               total_tokens=getattr(response.usage, "total_tokens", None))
            
            return response
            
        except Exception as e:
            if self.provider == "openai" and "schema" in str(e).lower() and self._supports_structured:
                logger.warning("Structured Outputs 실패, JSON 모드로 폴백", error=str(e)[:100])
                self._supports_structured = False
                return await self._call_with_schema(messages, schema, temperature, max_tokens)
            raise
    
    # @cache_manager.cache_result(ttl=3600, key_prefix="facts:")  # 캐시 완전 비활성화
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
                max_tokens=8000
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
    
    async def rewrite_for_user(self, facts: ExtractedFacts, profile: UserProfile, original_title: str = None) -> Dict[str, Any]:
        """사용자 맞춤 콘텐츠 분석 (제목은 절대 변경하지 않음)"""
        # 읽기 모드 완전 제거, 800자 기본
        guide = {"time": "2분", "style": "상세한 뉴스 분석"}
        
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
        
        system = f"""너는 전문 뉴스 기자다. JSON만 출력한다. 한국어로 작성한다.

🚨 CRITICAL: 2000자 미만 시 응답 거절됨
- 반드시 2000자 이상 작성
- 짧은 응답은 절대 금지
- 충분하지 않으면 다시 작성
- 상세하고 풍부한 내용 필수

구조:
1. 뉴스 사실 (1600자): 모든 배경, 맥락, 의미
2. {primary_job} 해석 (400자): 전문적 분석

절대 2000자 이상 작성하라!"""
        original_news_title = original_title or facts.what
        
        user = f"""
원본 제목: {original_news_title}
(절대 변경 금지)

뉴스 팩트 (모든 정보 포함하여 기사 작성):
- 누가: {', '.join(facts.who[:5])}
- 무엇: {facts.what}
- 언제: {facts.when}
- 어디서: {facts.where}  
- 왜: {facts.why}
- 어떻게: {facts.how}
- 수치: {json.dumps(facts.numbers, ensure_ascii=False)}
- 검증사실: {', '.join(facts.verified_facts)}

독자: {primary_job} ({profile.age}세)
관심사: {', '.join(all_interests[:3])}

🚨 무조건 2000자 이상 작성하라! 🚨
- 1999자 이하는 실패작으로 간주
- 뉴스 배경, 맥락, 의미를 모두 포함
- {primary_job} 관점 상세 분석
- 반복해서라도 2000자 채우기
- 짧은 답변은 거부됨

JSON:
{{
  "title": "{original_news_title}",
  "content": "뉴스내용+해석",
  "key_points": ["핵심1", "핵심2", "핵심3"],
  "reading_time": "{guide['time']}"
}}
"""
        
        async def _call():
            # dual 모드에서는 Groq 먼저 시도, 실패하면 OpenAI
            if self.provider == "dual":
                try:
                    # Groq 시도
                    self.client = self.groq_client
                    self.model = settings.groq_model
                    logger.info("개인화 시도: Groq 우선")
                    return await self._call_with_schema(
                        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                        schema={"name": "PersonalizedArticle", "schema": REWRITE_SCHEMA},
                        temperature=0.6,
                        max_tokens=8000
                    )
                except Exception as e:
                    # OpenAI로 fallback
                    logger.warning(f"Groq 실패, OpenAI 대체: {e}")
                    self.client = self.openai_client
                    self.model = settings.openai_model
                    return await self._call_with_schema(
                        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                        schema={"name": "PersonalizedArticle", "schema": REWRITE_SCHEMA},
                        temperature=0.6,
                        max_tokens=8000
                    )
            else:
                # 단일 모드
                return await self._call_with_schema(
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                    schema={"name": "PersonalizedArticle", "schema": REWRITE_SCHEMA},
                    temperature=0.6,
                    max_tokens=8000
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
            
            # 디버그: AI 실제 응답 확인
            logger.info("AI 실제 응답 확인",
                       ai_title=obj.get("title", "없음"),
                       ai_content_length=len(obj.get("content", "")),
                       original_title=original_news_title,
                       user_id=profile.user_id[:10])
            
            # 새로운 폴백 시스템 사용
            from .groq_fallback import run_personalize
            
            # 팩트 정보를 텍스트로 변환
            facts_text = f"""
제목: {original_news_title}
내용: {facts.what}
인물: {', '.join(facts.who[:3])}
시점: {facts.when}
배경: {facts.why}
"""
            
            # 프로필 정보를 dict로 변환
            profile_dict = {
                "role": primary_job,
                "interests": all_interests,
                "reading_mode": "insight"
            }
            
            # 폴백 시스템으로 개인화 실행
            result = await run_personalize(facts_text, profile_dict)
            
            return {
                "title": original_news_title,
                "content": result["personalized_article"],
                "personalized_article": result["personalized_article"],
                "key_points": [f"{primary_job} 관점 분석", "AI 기반 맞춤형 재구성", "실시간 뉴스 처리"],
                "reading_time": guide["time"],
                "disclaimer": f"본 분석은 {primary_job} 관점에서의 참고용 정보입니다.",
                "provider": result["provider"],
                "model": result.get("model", "unknown")
            }
            
        except Exception as e:
            logger.error("재작성 실패", error=str(e), user_id=profile.user_id[:10])
            return self._create_fallback_content(facts, guide, original_news_title)
    
    def _create_fallback_content(self, facts: ExtractedFacts, guide: Dict[str, Any], original_title: str = None) -> Dict[str, Any]:
        """재작성 실패 시 fallback 콘텐츠 생성"""
        return {
            "title": original_title or facts.what or "뉴스",
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