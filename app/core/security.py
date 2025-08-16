"""
보안 관련 유틸리티
"""
import hashlib
import uuid
from typing import Optional
from fastapi import HTTPException, Request
from .config import settings


def require_api_key(request: Request) -> None:
    """API 키 검증 (보안 강화)"""
    if not settings.internal_api_key:
        if settings.environment == "production":
            raise HTTPException(
                status_code=503, 
                detail="API key not configured in production"
            )
        return  # 개발 환경에서는 허용
    
    api_key = request.headers.get("X-API-Key")
    if api_key != settings.internal_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")


def get_client_ip(request: Request) -> str:
    """클라이언트 IP 추출 (프록시 환경 고려)"""
    client_ip = request.client.host if request.client else "anonymous"
    
    # 신뢰할 수 있는 프록시에서 온 요청만 헤더 확인
    if settings.trusted_proxies_list and client_ip in settings.trusted_proxies_list:
        # X-Forwarded-For 헤더 확인
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        # X-Real-IP 헤더 확인
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
    
    return client_ip


def generate_request_id() -> str:
    """요청 ID 생성"""
    return f"req_{uuid.uuid4().hex[:16]}"


def make_etag(payload: bytes) -> str:
    """ETag 생성 (FIPS 친화)"""
    return hashlib.blake2s(payload, digest_size=16).hexdigest()


def profile_hash(profile_data: dict) -> str:
    """프로필 캐시 해시 생성 (FIPS 친화)"""
    import json
    payload = json.dumps(profile_data, ensure_ascii=False, sort_keys=True)
    return hashlib.blake2s(payload.encode(), digest_size=12).hexdigest()