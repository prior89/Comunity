"""
애플리케이션 설정 관리
"""
import os
from typing import Optional, List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """환경별 설정 관리"""
    
    # 기본 설정
    app_name: str = "깔깔뉴스 API"
    app_version: str = "3.0.2"
    environment: str = "development"
    debug: bool = False
    
    # API 설정
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    openai_timeout: int = 60
    openai_retries: int = 2
    openai_concurrency_limit: int = 25
    
    # 보안 설정
    internal_api_key: Optional[str] = None
    trusted_proxies: List[str] = []
    
    # 데이터베이스 설정
    database_url: str = "sqlite:///kkalkalnews.db"
    redis_url: str = "redis://localhost:6379"
    
    # CORS 설정
    cors_origins: List[str] = ["http://localhost:3000"]
    
    # 성능 설정
    articles_per_batch: int = 5
    collect_timeout: int = 30
    summary_max: int = 2000
    min_content_len: int = 80  # 품질 향상을 위해 80자로 증가
    rate_limit_per_minute: int = 100
    
    # 캐시 설정
    pc_ttl_days: int = 30
    activity_ttl_days: int = 90
    collect_lock_ttl: int = 180
    
    # Structured Outputs 설정
    use_structured_outputs: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        
    @property
    def cors_origins_list(self) -> List[str]:
        """CORS origins를 리스트로 반환"""
        if isinstance(self.cors_origins, str):
            return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return self.cors_origins
    
    @property
    def trusted_proxies_list(self) -> List[str]:
        """신뢰할 수 있는 프록시를 리스트로 반환"""
        if isinstance(self.trusted_proxies, str):
            return [ip.strip() for ip in self.trusted_proxies.split(",") if ip.strip()]
        return self.trusted_proxies


# 전역 설정 인스턴스
settings = Settings()