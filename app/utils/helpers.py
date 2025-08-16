"""
유틸리티 헬퍼 함수들
"""
import re
import json
import hashlib
import asyncio
import random
from html import unescape
from typing import List, Dict, Any
from datetime import datetime
from email.utils import formatdate
from zoneinfo import ZoneInfo

from ..core.config import settings
from ..core.logging import get_logger

logger = get_logger("helpers")


def clean_html_summary(s: str, limit: int = None) -> str:
    """HTML 태그 제거 및 텍스트 정리"""
    if not s:
        return ""
    
    # HTML 태그 제거
    s = re.sub(r"<[^>]+>", " ", s)
    # HTML 엔티티 디코드
    s = unescape(s)
    # 여러 공백을 하나로
    s = re.sub(r"\s+", " ", s).strip()
    
    # 길이 제한
    max_len = limit if limit is not None else settings.summary_max
    return s[:max_len]


def clip_list(lst: List[str], max_items: int = 10, max_str_len: int = 50) -> List[str]:
    """리스트 길이 및 문자열 길이 제한"""
    return [str(x)[:max_str_len] for x in (lst or [])][:max_items]


def coerce_json(s: str) -> dict:
    """JSON 파싱 실패 시 복구 시도"""
    s = s.strip()
    # 코드블록 제거
    s = re.sub(r"^```json\s*|\s*```$", "", s)
    # 중괄호 영역만 추출
    m = re.search(r"\{.*\}\s*$", s, re.S)
    s = m.group(0) if m else s
    # 트레일링 콤마 제거
    s = re.sub(r",\s*([}\]])", r"\1", s)
    return json.loads(s)


def should_retry_openai(e: Exception) -> bool:
    """OpenAI 재시도 가능 여부 판단"""
    s = str(e).lower()
    # 재시도 불가능한 에러들
    non_retryable = ["401", "403", "invalid api key", "content_filter", "schema", "422", "bad request"]
    return not any(x in s for x in non_retryable)


async def with_retry(coro_fn, retries: int = 3, base_delay: float = 0.5, timeout: float = None):
    """지수 백오프와 함께 재시도"""
    if timeout is None:
        timeout = settings.openai_timeout + 5
    
    last_exception = None
    for i in range(retries):
        try:
            return await asyncio.wait_for(coro_fn(), timeout=timeout)
        except Exception as e:
            last_exception = e
            # 재시도 불가능한 에러거나 마지막 시도면 중단
            if i >= retries - 1 or not should_retry_openai(e):
                break
            
            # 지수 백오프 + 랜덤 지터
            jitter = random.uniform(0.5, 1.5)
            delay = base_delay * (2 ** i) * jitter
            await asyncio.sleep(delay)
            
            logger.warning("재시도 중", attempt=i+1, delay=delay, error=str(e)[:100])
    
    raise last_exception


def datetime_to_http_date(dt: datetime) -> str:
    """datetime을 HTTP Date 형식으로 변환"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    else:
        dt = dt.astimezone(ZoneInfo("UTC"))
    
    import calendar
    timestamp = calendar.timegm(dt.utctimetuple())
    return formatdate(timestamp, usegmt=True)


def make_safe_filename(text: str, max_length: int = 50) -> str:
    """안전한 파일명 생성"""
    # 특수문자 제거
    safe = re.sub(r'[^\w\s-]', '', text)
    # 공백을 언더스코어로
    safe = re.sub(r'[-\s]+', '_', safe)
    return safe[:max_length].strip('_')


def validate_article_content(article: Dict[str, Any]) -> bool:
    """기사 콘텐츠 유효성 검증"""
    required_fields = ['id', 'title', 'content', 'url', 'source']
    
    # 필수 필드 확인
    for field in required_fields:
        if not article.get(field):
            return False
    
    # 최소 콘텐츠 길이 확인
    if len(article['content']) < settings.min_content_len:
        return False
    
    # URL 형식 기본 검증
    url = article['url']
    if not (url.startswith('http://') or url.startswith('https://')):
        return False
    
    return True


def generate_article_id(url: str, published: str = None) -> str:
    """기사 ID 생성 (FIPS 친화)"""
    id_source = f"{url}_{published}" if published else url
    return hashlib.blake2s(id_source.encode(), digest_size=12).hexdigest()


def extract_numbers_from_text(text: str) -> Dict[str, str]:
    """텍스트에서 수치 정보 추출"""
    numbers = {}
    
    # 숫자 패턴 매칭
    patterns = [
        (r'(\d+(?:\.\d+)?)\s*%', '퍼센트'),
        (r'(\d+(?:,\d{3})*)\s*원', '원'),
        (r'(\d+(?:,\d{3})*)\s*명', '명'),
        (r'(\d+(?:,\d{3})*)\s*개', '개'),
        (r'(\d+(?:\.\d+)?)\s*배', '배'),
    ]
    
    for pattern, unit in patterns:
        matches = re.findall(pattern, text)
        if matches:
            numbers[unit] = matches[0]
    
    return numbers


class RateLimiter:
    """비동기 레이트 리미터"""
    
    def __init__(self, max_calls: int, time_window: int):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """레이트 리미트 확인 및 획득"""
        async with self._lock:
            now = asyncio.get_event_loop().time()
            
            # 시간 윈도우 밖의 호출 제거
            self.calls = [call_time for call_time in self.calls 
                         if now - call_time < self.time_window]
            
            # 최대 호출 수 확인
            if len(self.calls) >= self.max_calls:
                # 대기 시간 계산
                wait_time = self.time_window - (now - self.calls[0])
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    return await self.acquire()  # 재귀 호출
            
            # 호출 시간 기록
            self.calls.append(now)
            return True