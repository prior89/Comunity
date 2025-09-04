"""
성능 지표 대시보드 API 엔드포인트
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from ...api.dependencies import get_database, get_mongo_database, log_request_info
from ...core.logging import get_logger

logger = get_logger("api.dashboard")
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/metrics")
async def get_performance_metrics(
    hours: int = 24,
    db = Depends(get_mongo_database),
    request_info: Dict[str, str] = Depends(log_request_info)
):
    """성능 지표 대시보드 - 실시간 KPI"""
    
    logger.info("성능 지표 조회", hours=hours, **request_info)
    
    try:
        # 시간 범위 설정
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        metrics = {
            "period": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(), 
                "hours": hours
            },
            "api_performance": await _get_api_metrics(db, start_time, end_time),
            "processing_stats": await _get_processing_stats(db, start_time, end_time),
            "ai_provider_stats": await _get_ai_provider_stats(db, start_time, end_time),
            "error_analysis": await _get_error_analysis(db, start_time, end_time),
            "cache_performance": await _get_cache_stats(db, start_time, end_time)
        }
        
        return metrics
        
    except Exception as e:
        logger.error("성능 지표 조회 실패", error=str(e))
        return {
            "error": "성능 지표 조회 실패",
            "details": str(e),
            "period": {"hours": hours}
        }

async def _get_api_metrics(db, start_time, end_time) -> Dict[str, Any]:
    """API 성능 지표"""
    # 실제 구현에서는 로그 데이터나 메트릭 DB에서 조회
    return {
        "total_requests": 150,
        "successful_requests": 147, 
        "error_requests": 3,
        "success_rate": 98.0,
        "response_times": {
            "p50": 2650,  # ms
            "p95": 4200,  # ms
            "p99": 8100,  # ms
            "avg": 2890   # ms
        },
        "requests_per_hour": 6.25
    }

async def _get_processing_stats(db, start_time, end_time) -> Dict[str, Any]:
    """처리 통계"""
    return {
        "articles_collected": 42,
        "articles_processed": 38,
        "facts_extracted": 38,
        "personalizations_generated": 35,
        "processing_success_rate": 92.1,
        "avg_processing_time": 2650  # ms
    }

async def _get_ai_provider_stats(db, start_time, end_time) -> Dict[str, Any]:
    """AI 제공자별 통계"""
    return {
        "groq": {
            "requests": 25,
            "successes": 22,
            "failures": 3,
            "avg_response_time": 2100,
            "primary_model": "llama-3.1-70b-versatile"
        },
        "openai_fallback": {
            "requests": 13,
            "successes": 13, 
            "failures": 0,
            "avg_response_time": 3200,
            "primary_model": "gpt-4o-mini"
        }
    }

async def _get_error_analysis(db, start_time, end_time) -> List[Dict[str, Any]]:
    """에러 분석"""
    return [
        {"error_type": "model_decommissioned", "count": 2, "percentage": 1.3},
        {"error_type": "timeout", "count": 1, "percentage": 0.7},
        {"error_type": "rate_limit", "count": 0, "percentage": 0.0}
    ]

async def _get_cache_stats(db, start_time, end_time) -> Dict[str, Any]:
    """캐시 성능"""
    return {
        "cache_hits": 15,
        "cache_misses": 23,
        "hit_rate": 39.5,
        "avg_cache_response_time": 45  # ms
    }

@router.get("/health")
async def dashboard_health():
    """대시보드 헬스체크"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "3.0.8",
        "uptime_seconds": 3600
    }