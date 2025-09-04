"""
FastAPI 의존성 관리
"""
from typing import Optional, Dict
from fastapi import Depends, HTTPException, Request, Header

from ..core.security import require_api_key, get_client_ip
from ..core.logging import get_logger
from ..services.news_processor import NewsProcessor
from ..models.database import Database
from ..models.mongodb import MongoDatabase
from ..core.config import settings

logger = get_logger("dependencies")

# 전역 서비스 인스턴스들
_news_processor: Optional[NewsProcessor] = None
_database: Optional[Database] = None
_mongo_database: Optional[MongoDatabase] = None


def set_news_processor(processor: NewsProcessor) -> None:
    """뉴스 프로세서 설정"""
    global _news_processor
    _news_processor = processor


def set_database(database: Database) -> None:
    """데이터베이스 설정"""
    global _database
    _database = database


def set_mongo_database(database: MongoDatabase) -> None:
    """MongoDB 데이터베이스 설정"""
    global _mongo_database
    _mongo_database = database


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


def get_mongo_database() -> MongoDatabase:
    """MongoDB 데이터베이스 의존성"""
    if _mongo_database is None:
        raise HTTPException(status_code=503, detail="MongoDB not available")
    return _mongo_database


def get_active_database():
    """활성 데이터베이스 반환 (MongoDB 우선)"""
    if settings.use_mongodb and _mongo_database is not None:
        return _mongo_database
    return get_database()


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


def verify_internal_key(
    request: Request,
    authorization: str = Header(default=None),
    x_internal_api_key: str = Header(default=None, alias="X-Internal-Api-Key"),
):
    """유연한 내부키 검증 - 다양한 헤더 방식 지원"""
    expected = getattr(settings, 'internal_api_key', None)
    if not expected or not expected.strip():
        # 키가 설정 안 되어 있으면 스킵 (데모 편의)
        return True

    expected = expected.strip()
    got = None
    
    if x_internal_api_key:
        got = x_internal_api_key.strip()
    elif authorization and authorization.lower().startswith("bearer "):
        got = authorization.split(" ", 1)[1].strip()
    else:
        # query parameter 또는 다른 헤더에서도 확인
        got = (request.query_params.get("key") or 
               request.headers.get("X-API-Key") or "").strip()

    if got != expected:
        logger.warning("내부키 검증 실패", 
                      expected_length=len(expected),
                      got_length=len(got) if got else 0)
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    return True