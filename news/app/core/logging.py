"""
구조화된 로깅 시스템
"""
import json
import logging
import contextvars
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

# Request ID 컨텍스트 변수
_request_id_ctx = contextvars.ContextVar("request_id", default=None)

# 타임존 설정
KST = ZoneInfo("Asia/Seoul")


def now_kst() -> str:
    """현재 시간을 KST로 반환"""
    return datetime.now(tz=KST).isoformat()


def setup_logging():
    """로깅 설정 초기화"""
    logger = logging.getLogger("kkalkal")
    
    if not logger.handlers:  # 중복 핸들러 방지
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    logger.setLevel(logging.INFO)
    return logger


def set_request_id(request_id: str) -> contextvars.Token:
    """Request ID 설정"""
    return _request_id_ctx.set(request_id)


def reset_request_id(token: contextvars.Token) -> None:
    """Request ID 리셋"""
    _request_id_ctx.reset(token)


def log_json(level: str = "INFO", **kwargs: Any) -> None:
    """구조화된 JSON 로그 출력"""
    logger = logging.getLogger("kkalkal")
    
    # Request ID 자동 추가
    request_id = _request_id_ctx.get()
    if request_id:
        kwargs.setdefault("request_id", request_id)
    
    # 타임스탬프 추가
    kwargs["timestamp"] = now_kst()
    kwargs["level"] = level
    
    try:
        log_message = json.dumps(kwargs, ensure_ascii=False, default=str)
        getattr(logger, level.lower(), logger.info)(log_message)
    except Exception:
        logger.error(f"Failed to log: {kwargs}")


class StructuredLogger:
    """구조화된 로거 클래스"""
    
    def __init__(self, name: str):
        self.name = name
    
    def info(self, message: str, **kwargs: Any) -> None:
        log_json(level="INFO", message=message, logger=self.name, **kwargs)
    
    def warning(self, message: str, **kwargs: Any) -> None:
        log_json(level="WARNING", message=message, logger=self.name, **kwargs)
    
    def error(self, message: str, **kwargs: Any) -> None:
        log_json(level="ERROR", message=message, logger=self.name, **kwargs)
    
    def debug(self, message: str, **kwargs: Any) -> None:
        log_json(level="DEBUG", message=message, logger=self.name, **kwargs)


def get_logger(name: str) -> StructuredLogger:
    """구조화된 로거 인스턴스 반환"""
    return StructuredLogger(name)