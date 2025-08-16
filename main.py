"""
깔깔뉴스 API 메인 애플리케이션 (v3.0.0)
모듈화된 아키텍처 + 2025년 최적화 적용
"""
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.models.database import Database
from app.services.news_processor import NewsProcessor
from app.api.dependencies import set_news_processor, set_database
from app.api.routes import news, users, system
from app.middleware import RateLimitMiddleware, RequestLoggingMiddleware
from app.utils.cache import cache_manager

# 로깅 초기화
setup_logging()
logger = get_logger("main")

# 전역 변수
processor: NewsProcessor = None
database: Database = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 라이프사이클 관리"""
    global processor, database
    
    # 시작 시 초기화
    logger.info("애플리케이션 시작", 
               version=settings.app_version,
               environment=settings.environment)
    
    # 환경 검증
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY 환경변수가 필요합니다")
    
    if settings.environment == "production" and not settings.internal_api_key:
        raise RuntimeError("프로덕션 환경에서는 INTERNAL_API_KEY가 필요합니다")
    
    # 데이터베이스 초기화
    database = Database()
    set_database(database)
    
    # 뉴스 프로세서 초기화
    processor = NewsProcessor(settings.openai_api_key)
    set_news_processor(processor)
    
    # 시스템 상태 확인
    health_checks = await processor.health_check()
    logger.info("시스템 초기화 완료", health_checks=health_checks)
    
    # 백그라운드 작업 시작
    cleanup_task = asyncio.create_task(periodic_cleanup())
    initial_collection_task = asyncio.create_task(initial_news_collection())
    
    logger.info("서비스 준비 완료",
               features={
                   "structured_outputs": settings.use_structured_outputs,
                   "redis_cache": cache_manager._cache_enabled,
                   "rate_limiting": True,
                   "distributed_locks": True
               })
    
    yield
    
    # 종료 시 정리
    logger.info("애플리케이션 종료 중...")
    
    # 백그라운드 작업 취소
    cleanup_task.cancel()
    initial_collection_task.cancel()
    
    # 진행 중인 작업들 정리
    try:
        await asyncio.wait_for(
            asyncio.gather(cleanup_task, initial_collection_task, return_exceptions=True),
            timeout=5.0
        )
    except asyncio.TimeoutError:
        logger.warning("백그라운드 작업 정리 타임아웃")
    
    logger.info("애플리케이션 종료 완료")


async def initial_news_collection():
    """초기 뉴스 수집"""
    try:
        await asyncio.sleep(2)  # 시작 지연
        await processor.process_news_batch()
        logger.info("초기 뉴스 수집 완료")
    except Exception as e:
        logger.error("초기 뉴스 수집 실패", error=str(e))


async def periodic_cleanup():
    """주기적 데이터 정리"""
    while True:
        try:
            # 24시간마다 정리
            await asyncio.sleep(24 * 3600)
            
            result = database.cleanup_old_data()
            logger.info("주기적 데이터 정리 완료",
                       pc_deleted=result["pc_deleted"],
                       activity_deleted=result["activity_deleted"])
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("주기적 데이터 정리 실패", error=str(e))


# FastAPI 앱 생성
app = FastAPI(
    title=settings.app_name,
    description="AI 기반 완전 맞춤형 뉴스 플랫폼 (모듈화된 아키텍처)",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None
)

# CORS 설정
if settings.cors_origins_list == ["*"]:
    logger.warning("CORS 와일드카드 사용 중 - 프로덕션에서는 특정 도메인 설정 권장")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-Request-ID"],
        expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"]
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-Request-ID"],
        expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
        max_age=3600
    )

# 미들웨어 추가 (순서 중요)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware, 
                  capacity=60, 
                  refill_rate=20)

# 라우터 등록
app.include_router(news.router)
app.include_router(users.router)
app.include_router(system.router)

# 루트 엔드포인트
@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "environment": settings.environment,
        "docs": "/docs" if settings.debug else "disabled"
    }


# 개발 서버 실행
if __name__ == "__main__":
    import uvicorn
    
    logger.info("개발 서버 시작", port=8000)
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info"
    )