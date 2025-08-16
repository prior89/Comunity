"""
캐시 시스템 (Redis 기반)
"""
import json
import asyncio
from typing import Any, Optional, Callable
from functools import wraps

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from ..core.config import settings
from ..core.logging import get_logger

logger = get_logger("cache")


class CacheManager:
    """Redis 캐시 관리자"""
    
    def __init__(self):
        self.redis_client = None
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
            except Exception as e:
                logger.warning("Redis 연결 실패, 메모리 캐시 사용", error=str(e))
        
        # 메모리 캐시 fallback
        self._memory_cache = {}
        self._cache_enabled = self.redis_client is not None
    
    async def get(self, key: str) -> Optional[Any]:
        """캐시에서 값 조회"""
        if not self._cache_enabled:
            return self._memory_cache.get(key)
        
        try:
            value = await self.redis_client.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.warning("Redis 조회 실패", key=key[:50], error=str(e))
        
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """캐시에 값 저장"""
        if not self._cache_enabled:
            self._memory_cache[key] = value
            # 메모리 캐시 크기 제한
            if len(self._memory_cache) > 1000:
                # 오래된 항목 제거 (단순 FIFO)
                oldest_key = next(iter(self._memory_cache))
                del self._memory_cache[oldest_key]
            return
        
        try:
            serialized = json.dumps(value, ensure_ascii=False, default=str)
            await self.redis_client.setex(key, ttl, serialized)
        except Exception as e:
            logger.warning("Redis 저장 실패", key=key[:50], error=str(e))
    
    async def delete(self, key: str) -> None:
        """캐시에서 값 삭제"""
        if not self._cache_enabled:
            self._memory_cache.pop(key, None)
            return
        
        try:
            await self.redis_client.delete(key)
        except Exception as e:
            logger.warning("Redis 삭제 실패", key=key[:50], error=str(e))
    
    async def health_check(self) -> bool:
        """캐시 시스템 상태 확인"""
        if not self._cache_enabled:
            return True  # 메모리 캐시는 항상 사용 가능
        
        try:
            await self.redis_client.ping()
            return True
        except Exception:
            return False
    
    def cache_result(self, ttl: int = 3600, key_prefix: str = ""):
        """함수 결과 캐시 데코레이터"""
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # 캐시 키 생성
                cache_key = f"{key_prefix}{func.__name__}:{hash(str(args) + str(kwargs))}"
                
                # 캐시 조회
                cached_result = await self.get(cache_key)
                if cached_result is not None:
                    logger.debug("캐시 히트", function=func.__name__, key=cache_key[:50])
                    return cached_result
                
                # 함수 실행
                result = await func(*args, **kwargs)
                
                # 캐시 저장
                await self.set(cache_key, result, ttl)
                logger.debug("캐시 저장", function=func.__name__, key=cache_key[:50])
                
                return result
            return wrapper
        return decorator


# 전역 캐시 매니저 인스턴스
cache_manager = CacheManager()