"""
강건한 팩트 추출 시스템 - JSON 강제 + 재시도 + 안전한 기본값
"""
import json
import asyncio
from openai import AsyncOpenAI
from ..core.logging import get_logger
from ..core.config import settings

logger = get_logger("fact_extraction")

async def extract_facts(text: str):
    """팩트 추출 - 절대 실패하지 않는 강건한 시스템"""
    
    system = (
        "뉴스에서 5W1H만 JSON으로 추출한다. "
        "키: who(리스트), what, when, where(리스트), why, how, confidence(0~1). "
        "모르는 값은 null. 설명/주석 금지. JSON만 출력."
    )
    
    user_prompt = f"다음 기사에서 5W1H를 추출해. 반드시 JSON만 출력:\n{text[:2000]}"
    
    oai = AsyncOpenAI(
        api_key=settings.openai_api_key,
        timeout=20
    )
    
    last_error = None
    
    # 3회 재시도
    for attempt in range(3):
        try:
            r = await oai.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},  # JSON 강제
                temperature=0,  # 일관된 결과
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt}
                ],
            )
            
            content = r.choices[0].message.content
            data = json.loads(content)
            
            # 필수 필드 보장
            data.setdefault("who", [])
            data.setdefault("what", text[:100] + "..." if text else "정보 없음")
            data.setdefault("when", None)  
            data.setdefault("where", [])
            data.setdefault("why", None)
            data.setdefault("how", None)
            data.setdefault("confidence", 0.7)
            
            logger.info("팩트 추출 성공", confidence=data.get("confidence", 0))
            return data
            
        except Exception as e:
            last_error = e
            logger.warning(f"팩트 추출 재시도 {attempt+1}/3", error=str(e)[:100])
            await asyncio.sleep(2**attempt)  # 백오프
    
    # 모든 시도 실패 시 안전한 기본값
    logger.error("팩트 추출 완전 실패, 기본값 반환", error=str(last_error))
    return {
        "who": [],
        "what": text[:100] + "..." if text else "뉴스 내용",
        "when": None,
        "where": [],
        "why": None,
        "how": None,
        "confidence": 0.0,
        "error": str(last_error)[:160]
    }