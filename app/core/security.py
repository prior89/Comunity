"""
보안 관련 유틸리티
"""
import hashlib
import uuid
import ipaddress
from typing import Optional, List
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


def _parse_trusted_proxies(items: List[str]):
    """신뢰 프록시 CIDR 파싱 (2025년 보안 강화)"""
    networks = []
    for item in items:
        try:
            if "/" in item:
                # CIDR 표기법
                networks.append(ipaddress.ip_network(item, strict=False))
            else:
                # 단일 IP를 /32 또는 /128로 변환
                if ":" in item:
                    networks.append(ipaddress.ip_network(f"{item}/128", strict=False))
                else:
                    networks.append(ipaddress.ip_network(f"{item}/32", strict=False))
        except Exception:
            continue  # 잘못된 형식은 무시
    return networks


def _is_trusted_proxy(ip: str, trusted_networks) -> bool:
    """IP가 신뢰 프록시 네트워크에 속하는지 확인"""
    try:
        addr = ipaddress.ip_address(ip)
        return any(addr in network for network in trusted_networks)
    except Exception:
        return False


# 신뢰 프록시 네트워크 파싱 (애플리케이션 시작시 1회)
_TRUSTED_NETWORKS = _parse_trusted_proxies(settings.trusted_proxies_list) if settings.trusted_proxies_list else []


def get_client_ip(request: Request) -> str:
    """클라이언트 IP 추출 (CIDR 지원 프록시 환경)"""
    client_ip = request.client.host if request.client else "anonymous"
    
    # CIDR 기반 신뢰 프록시 확인
    if _TRUSTED_NETWORKS and _is_trusted_proxy(client_ip, _TRUSTED_NETWORKS):
        # X-Forwarded-For 헤더 확인 (첫 번째 IP)
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