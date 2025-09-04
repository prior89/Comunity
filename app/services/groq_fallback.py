"""
Groq 모델 자동 폴백 시스템 - 모델 폐기 시 자동 대응
"""
import os
import asyncio
from groq import AsyncGroq, APIStatusError, APIConnectionError, APITimeoutError, RateLimitError
from openai import AsyncOpenAI
from ..core.logging import get_logger

logger = get_logger("groq_fallback")

# 환경변수에서 모델 설정
GROQ_MODEL = os.getenv("GROQ_MODEL", "").strip()
GROQ_MODEL_CANDIDATES = [m.strip() for m in os.getenv("GROQ_MODEL_CANDIDATES", "").split(",") if m.strip()]
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def _is_model_decommissioned(e: Exception) -> bool:
    """모델 폐기/지원 중단 에러 감지"""
    s = str(e).lower()
    return any(keyword in s for keyword in [
        "decommissioned", "no longer supported", "model not found", 
        "invalid model", "model has been deprecated"
    ])

async def _try_groq(messages, temperature=0.2, max_tokens=900):
    """Groq 모델 후보들 순회 시도"""
    if not GROQ_MODEL and not GROQ_MODEL_CANDIDATES:
        return None, "no_groq_model_configured"
    
    client = AsyncGroq(timeout=20)
    candidates = ([GROQ_MODEL] if GROQ_MODEL else []) + GROQ_MODEL_CANDIDATES
    
    last_err = None
    for model_name in candidates:
        logger.info(f"Groq 모델 시도: {model_name}")
        
        for attempt in range(3):  # 모델당 3회 재시도
            try:
                r = await client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                txt = (r.choices[0].message.content or "").strip()
                if txt:
                    logger.info(f"Groq 성공: {model_name}")
                    return {
                        "provider": "groq",
                        "model": model_name, 
                        "personalized_article": txt,
                        "is_fallback": False
                    }, None
                last_err = ValueError("empty response")
                
            except (RateLimitError, APIConnectionError, APITimeoutError) as e:
                last_err = e
                await asyncio.sleep(2**attempt)  # 백오프
                logger.warning(f"Groq 재시도 {attempt+1}/3: {model_name} - {e}")
                
            except APIStatusError as e:
                last_err = e
                if _is_model_decommissioned(e):
                    logger.warning(f"Groq 모델 폐기됨: {model_name} - {e}")
                    break  # 이 모델은 포기, 다음 후보로
                await asyncio.sleep(2**attempt)
                logger.warning(f"Groq API 에러 재시도 {attempt+1}/3: {model_name} - {e}")
        
        # 다음 후보 모델로 진행
        logger.warning(f"Groq 모델 실패, 다음 후보로: {model_name}")
    
    return None, last_err

async def run_personalize(article_text: str, profile: dict):
    """완전 방어형 개인화 - 절대 실패하지 않음"""
    role = profile.get("role") or "투자자"
    mode = (profile.get("reading_mode") or "insight").lower()
    
    # reading_mode 기반 스타일 결정
    style = {
        "insight": "맥락과 함의까지 담은 5~8문단 심층 기사",
        "brief": "핵심만 4~6문장 간결 기사", 
        "bullet": "핵심 포인트 6~8개 불릿",
    }.get(mode, "맥락과 함의까지 담은 5~8문단 심층 기사")

    sys = f"너는 사용자의 직업 관점으로 뉴스를 재작성한다. 출력 형식: {style}. 한국어로만 출력."
    user = f"[직업:{role}]\n아래 기사를 재작성:\n---\n{article_text}\n---"
    messages = [{"role": "system", "content": sys}, {"role": "user", "content": user}]

    # 1) Groq 우선 (자동 폴백 시스템)
    groq_result, groq_err = await _try_groq(messages)
    if groq_result:
        return groq_result

    # 2) OpenAI 폴백 (항상 동일 스키마)
    logger.info("OpenAI 폴백 실행", groq_error=str(groq_err) if groq_err else None)
    try:
        oai = AsyncOpenAI(timeout=20)
        r = await oai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.2
        )
        txt = (r.choices[0].message.content or "").strip() or f"(폴백 본문; groq 실패: {str(groq_err)[:120]})"
        
        return {
            "provider": "openai_fallback",
            "model": OPENAI_MODEL,
            "personalized_article": txt,
            "is_fallback": True,
            "groq_error": str(groq_err)[:200] if groq_err else None
        }
        
    except Exception as openai_err:
        # 마지막 안전장치
        logger.error("OpenAI도 실패", error=str(openai_err))
        return {
            "provider": "stub",
            "model": "none",
            "personalized_article": f"AI 서비스 일시 중단. 원본: {article_text[:500]}...",
            "is_fallback": True,
            "groq_error": str(groq_err)[:200] if groq_err else None,
            "openai_error": str(openai_err)[:200]
        }