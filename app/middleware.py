"""
미들웨어 모음
"""
import asyncio
import math
import random
from time import monotonic
from typing import Dict, Tuple
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .core.config import settings
from .core.security import get_client_ip, generate_request_id
from .core.logging import get_logger, set_request_id, reset_request_id

logger = get_logger("middleware")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """토큰 버킷 기반 레이트 리미터 (2025년 최적화 버전)"""
    
    def __init__(self, app, capacity: int = 60, refill_rate: int = 20):
        super().__init__(app)
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.buckets: Dict[str, Tuple[float, float]] = {}  # ip -> (tokens, last_ts)
        
        # 비동기 정리 작업
        self._cleanup_task = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """정리 작업 시작"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
    
    async def _periodic_cleanup(self):
        """주기적으로 오래된 버킷 정리"""
        while True:
            await asyncio.sleep(300)  # 5분마다 정리
            try:
                now = monotonic()
                cutoff = now - 3600  # 1시간 이상 사용하지 않은 버킷 제거
                
                old_buckets = [ip for ip, (_, last_ts) in self.buckets.items() if last_ts < cutoff]
                for ip in old_buckets:
                    del self.buckets[ip]
                
                if old_buckets:
                    logger.debug("레이트리미터 버킷 정리", removed_count=len(old_buckets))
                
            except Exception as e:
                logger.error("레이트리미터 정리 실패", error=str(e))
    
    async def dispatch(self, request: Request, call_next):
        ip = get_client_ip(request)
        tokens, last_ts = self.buckets.get(ip, (self.capacity, monotonic()))
        now = monotonic()
        
        # 토큰 리필
        tokens = min(self.capacity, tokens + (now - last_ts) * self.refill_rate)
        
        # 경로별 가중치 설정
        path = request.url.path
        if path.startswith("/api/news/refresh") or path.startswith("/api/news/personalize"):
            need = 3  # 무거운 작업
        elif path.startswith("/api/users"):
            need = 2  # 중간 작업
        else:
            need = 1  # 가벼운 작업
        
        if tokens < need:
            # 429 응답
            retry_after = max(1, math.ceil((need - tokens) / self.refill_rate))
            self.buckets[ip] = (tokens, now)
            
            logger.warning("레이트 리미트 초과", 
                          ip=ip, 
                          path=path, 
                          tokens=tokens, 
                          need=need,
                          retry_after=retry_after)
            
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={
                    "detail": "Too Many Requests",
                    "retry_after": retry_after,
                    "remaining_tokens": max(0, int(tokens))
                }
            )
        
        # 토큰 차감
        self.buckets[ip] = (tokens - need, now)
        
        # 요청 처리
        response = await call_next(request)
        
        # 레이트 리미트 헤더 추가
        remaining = max(0, int(self.buckets.get(ip, (0, now))[0]))
        response.headers["X-RateLimit-Limit"] = str(self.capacity)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        # 다음 토큰까지의 대기 시간
        if remaining < 1:
            wait = max(1, math.ceil((1.0 - remaining) / self.refill_rate))
            response.headers["X-RateLimit-Reset"] = str(wait)
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """요청 로깅 미들웨어"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = monotonic()
        
        # Request ID 생성 및 설정
        request_id = request.headers.get("X-Request-ID") or generate_request_id()
        token = set_request_id(request_id)
        
        # 클라이언트 정보
        client_ip = get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "")[:100]
        
        try:
            # 요청 로그
            logger.info("요청 시작",
                       method=request.method,
                       path=str(request.url.path),
                       query=str(request.url.query)[:200] if request.url.query else None,
                       ip=client_ip,
                       user_agent=user_agent)
            
            # 요청 처리
            response = await call_next(request)
            
            # 응답 헤더에 Request ID 추가
            response.headers["X-Request-ID"] = request_id
            
            # 성공 로그
            duration = round(monotonic() - start_time, 3)
            logger.info("요청 완료",
                       method=request.method,
                       path=str(request.url.path),
                       status=response.status_code,
                       ip=client_ip,
                       duration=duration)
            
            return response
            
        except Exception as e:
            # 에러 로그
            duration = round(monotonic() - start_time, 3)
            logger.error("요청 실패",
                        method=request.method,
                        path=str(request.url.path),
                        ip=client_ip,
                        duration=duration,
                        error=str(e)[:200])
            raise
        finally:
            # Request ID 컨텍스트 리셋
            reset_request_id(token)


class CORSMiddleware:
    """CORS 처리 미들웨어 (정적 설정)"""
    
    @staticmethod
    def add_cors_headers(response: Response, origin: str = None) -> Response:
        """CORS 헤더 추가"""
        
        # Origin 검증
        allowed_origins = settings.cors_origins_list
        if "*" in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Credentials"] = "false"
        elif origin and origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        
        # 기본 CORS 헤더
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-API-Key, X-Request-ID"
        response.headers["Access-Control-Expose-Headers"] = "X-Request-ID, X-RateLimit-Limit, X-RateLimit-Remaining"
        response.headers["Access-Control-Max-Age"] = "3600"
        
        # Vary 헤더 (캐싱 최적화)
        if "*" not in allowed_origins:
            response.headers["Vary"] = "Origin"
        
        return response