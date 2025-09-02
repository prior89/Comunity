"""
FastAPI 의존성 관리
"""
from typing import Optional, Dict
from fastapi import Depends, HTTPException, Request

from ..core.security import require_api_key, get_client_ip
from ..core.logging import get_logger
from ..services.news_processor import NewsProcessor
from ..models.database import Database

logger = get_logger("dependencies")

# 전역 서비스 인스턴스들
_news_processor: Optional[NewsProcessor] = None
_database: Optional[Database] = None


def set_news_processor(processor: NewsProcessor) -> None:
    """뉴스 프로세서 설정"""
    global _news_processor
    _news_processor = processor


def set_database(database: Database) -> None:
    """데이터베이스 설정"""
    global _database
    _database = database


def get_news_processor() -> NewsProcessor:
    """뉴스 프로세서 의존성"""
    if _news_processor is None:
        raise HTTPException(status_code=503, detail="Service is starting, try again")
    return _news_processor


def get_database() -> Database:
    """데이터베이스 의존성"""
    if _database is None:
        raise HTTPException(status_code=503, detail="Database not available")
    return _database


def require_write_permission(request: Request) -> None:
    """쓰기 권한 확인"""
    require_api_key(request)
    logger.debug("API 키 검증 성공", ip=get_client_ip(request))


def log_request_info(request: Request) -> Dict[str, str]:
    """요청 정보 로깅"""
    info = {
        "method": request.method,
        "path": str(request.url.path),
        "client_ip": get_client_ip(request),
        "user_agent": request.headers.get("User-Agent", "")[:100]
    }
    return info