"""
시스템 관련 API 엔드포인트 (헬스체크, 메트릭스 등)
"""
from typing import Dict, Any
from fastapi import APIRouter, Depends, Request
from datetime import datetime

from ...models.schemas import HealthCheck
from ...api.dependencies import get_news_processor, get_database, log_request_info
from ...services.news_processor import NewsProcessor
from ...models.database import Database
from ...core.config import settings
from ...core.logging import get_logger

logger = get_logger("api.system")

# Prometheus 메트릭 (선택적 임포트)
try:
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

router = APIRouter(prefix="/api/system", tags=["system"])

# v3.0.1 추가: 간단한 헬스체크 엔드포인트
@router.get("/healthz")
async def healthz():
    """Kubernetes 스타일 헬스체크 (라이브니스)"""
    return {"ok": True, "version": settings.app_version, "timestamp": datetime.now().isoformat()}

@router.get("/readyz") 
async def readyz():
    """Kubernetes 스타일 준비 상태 체크 (레디니스)"""
    return {"ready": True, "timestamp": datetime.now().isoformat()}

@router.get("/metrics")
async def metrics():
    """Prometheus 메트릭 노출 (2025년 모니터링 표준)"""
    if not PROMETHEUS_AVAILABLE:
        raise HTTPException(status_code=501, detail="Prometheus 클라이언트가 설치되지 않았습니다")
    
    from fastapi import Response
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/health", response_model=HealthCheck)
async def health_check(
    processor: NewsProcessor = Depends(get_news_processor),
    request_info: Dict[str, str] = Depends(log_request_info)
):
    """시스템 상태 확인"""
    
    logger.debug("헬스체크 요청", **request_info)
    
    # 각 컴포넌트 상태 확인
    checks = await processor.health_check()
    
    # 전체 상태 판단
    all_healthy = all(checks.values())
    status = "healthy" if all_healthy else "unhealthy"
    
    logger.info("헬스체크 완료", status=status, checks=checks)
    
    return HealthCheck(
        status=status,
        checks=checks,
        timestamp=datetime.now()
    )


@router.get("/info")
async def system_info(
    request_info: Dict[str, str] = Depends(log_request_info)
):
    """시스템 정보"""
    
    logger.debug("시스템 정보 요청", **request_info)
    
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "openai_model": settings.openai_model,
        "concurrency_limit": settings.openai_concurrency_limit,
        "rate_limit": settings.rate_limit_per_minute,
        "features": {
            "structured_outputs": settings.use_structured_outputs,
            "redis_cache": True,  # cache_manager에서 확인 가능
            "distributed_locks": True
        }
    }


@router.get("/stats")
async def system_stats(
    db: Database = Depends(get_database),
    request_info: Dict[str, str] = Depends(log_request_info)
):
    """시스템 통계"""
    
    logger.debug("시스템 통계 요청", **request_info)
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 기사 통계
            cursor.execute("SELECT COUNT(*) as total FROM original_articles")
            total_articles = cursor.fetchone()['total']
            
            # 사용자 통계
            cursor.execute("SELECT COUNT(*) as total FROM user_profiles")
            total_users = cursor.fetchone()['total']
            
            # 개인화 콘텐츠 통계
            cursor.execute("SELECT COUNT(*) as total FROM personalized_content")
            personalized_content = cursor.fetchone()['total']
            
            # 최근 활동 통계 (24시간)
            from datetime import datetime, timedelta
            yesterday = (datetime.now() - timedelta(days=1)).isoformat()
            cursor.execute(
                "SELECT COUNT(*) as total FROM user_activity WHERE created_at > ?", 
                (yesterday,)
            )
            recent_activities = cursor.fetchone()['total']
            
            # 최근 수집 기사 (24시간)
            cursor.execute(
                "SELECT COUNT(*) as total FROM original_articles WHERE collected_at > ?", 
                (yesterday,)
            )
            recent_articles = cursor.fetchone()['total']
        
        stats = {
            "articles": {
                "total": total_articles,
                "recent_24h": recent_articles
            },
            "users": {
                "total": total_users
            },
            "personalized_content": {
                "total": personalized_content
            },
            "activities": {
                "recent_24h": recent_activities
            }
        }
        
        logger.debug("시스템 통계 응답", stats=stats)
        return stats
        
    except Exception as e:
        logger.error("시스템 통계 조회 실패", error=str(e))
        return {
            "error": "통계 정보를 가져올 수 없습니다",
            "articles": {"total": 0, "recent_24h": 0},
            "users": {"total": 0},
            "personalized_content": {"total": 0},
            "activities": {"recent_24h": 0}
        }


@router.post("/cleanup")
async def cleanup_old_data(
    db: Database = Depends(get_database),
    request_info: Dict[str, str] = Depends(log_request_info)
):
    """오래된 데이터 정리"""
    
    logger.info("데이터 정리 요청", **request_info)
    
    try:
        result = db.cleanup_old_data()
        
        logger.info("데이터 정리 완료", 
                   pc_deleted=result["pc_deleted"],
                   activity_deleted=result["activity_deleted"])
        
        return {
            "message": "데이터 정리가 완료되었습니다",
            "deleted": result
        }
        
    except Exception as e:
        logger.error("데이터 정리 실패", error=str(e))
        return {
            "error": "데이터 정리 중 오류가 발생했습니다",
            "details": str(e)
        }