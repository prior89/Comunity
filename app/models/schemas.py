"""
Pydantic 스키마 정의
"""
from datetime import datetime
from typing import Dict, List, Optional, Literal
from dataclasses import dataclass
from pydantic import BaseModel, Field, model_validator


# Pydantic 버전 호환성
try:
    from pydantic import ConfigDict
    class StrictModel(BaseModel):
        """예상치 못한 필드를 차단하는 엄격한 모델 (v2)"""
        model_config = ConfigDict(extra="forbid")
except ImportError:
    class StrictModel(BaseModel):
        """예상치 못한 필드를 차단하는 엄격한 모델 (v1)"""
        class Config:
            extra = "forbid"


# 상수 정의
MAX_INTERESTS = 10
MAX_JOB_CATEGORIES = 8
VALID_ACTIONS = {"view", "click", "finish", "share", "like", "bookmark"}


@dataclass
class UserProfile:
    """사용자 프로필 데이터클래스"""
    user_id: str
    age: int
    gender: str
    location: str
    job_categories: List[str]
    interests_finance: List[str]
    interests_lifestyle: List[str]
    interests_hobby: List[str]
    interests_tech: List[str]
    work_style: str
    family_status: str
    living_situation: str
    reading_mode: str
    created_at: str
    updated_at: str


@dataclass
class ExtractedFacts:
    """추출된 팩트 데이터클래스"""
    who: List[str]
    what: str
    when: str
    where: str
    why: str
    how: str
    numbers: Dict[str, str]
    quotes: List[Dict[str, str]]
    verified_facts: List[str]


# Pydantic 모델들
class UserProfileCreate(StrictModel):
    """프로필 생성 요청"""
    age: int = Field(ge=20, le=70)
    gender: Literal["male", "female", "other"]
    location: str = Field(max_length=100)
    
    job_categories: List[str] = Field(max_length=MAX_JOB_CATEGORIES)
    interests_finance: List[str] = Field(default_factory=list, max_length=MAX_INTERESTS)
    interests_lifestyle: List[str] = Field(default_factory=list, max_length=MAX_INTERESTS)
    interests_hobby: List[str] = Field(default_factory=list, max_length=MAX_INTERESTS)
    interests_tech: List[str] = Field(default_factory=list, max_length=MAX_INTERESTS)
    
    work_style: Literal["commute", "remote", "flexible", "shift", "freelance", "hybrid"]
    family_status: Literal["single", "dating", "married", "divorced"]
    living_situation: Literal["alone", "family", "parents", "share"]
    
    reading_mode: Literal["quick", "standard", "deep", "detailed"] = "standard"


class UserProfileCreateRequest(BaseModel):
    """프로필 생성 요청 (user_id 포함, 한글 지원)"""
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    
    user_id: str = Field(max_length=64)
    age: int = Field(ge=20, le=70)
    gender: Literal["male", "female", "other"]
    location: str = Field(max_length=100)
    
    job_categories: List[str] = Field(max_length=MAX_JOB_CATEGORIES)
    interests_finance: List[str] = Field(default_factory=list, max_length=MAX_INTERESTS)
    interests_lifestyle: List[str] = Field(default_factory=list, max_length=MAX_INTERESTS)
    interests_hobby: List[str] = Field(default_factory=list, max_length=MAX_INTERESTS)
    interests_tech: List[str] = Field(default_factory=list, max_length=MAX_INTERESTS)
    
    work_style: Literal["commute", "remote", "flexible", "shift", "freelance", "hybrid"]
    family_status: Literal["single", "dating", "married", "divorced"]
    living_situation: Literal["alone", "family", "parents", "share"]
    
    reading_mode: Literal["quick", "standard", "deep", "detailed"] = "standard"


class PersonalizeRequest(BaseModel):
    """개인화 요청 (유연한 스키마 - 다양한 프론트 키 지원)"""
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True, populate_by_name=True)
    
    article_id: str = Field(max_length=50, alias="article")
    user_id: str = Field(max_length=64, alias="role")
    
    @model_validator(mode="before")
    @classmethod
    def coerce_keys(cls, v):
        """다양한 프런트 키들을 표준 키로 변환"""
        if isinstance(v, dict):
            v = dict(v)
            # article_id 별칭들
            v.setdefault("article_id", v.get("article") or v.get("content") or v.get("text"))
            # user_id 별칭들  
            v.setdefault("user_id", v.get("role") or v.get("persona") or v.get("job"))
        return v


class ActivityLog(StrictModel):
    """활동 로그"""
    user_id: str = Field(max_length=64)
    article_id: str = Field(max_length=50)
    action: Literal["view", "click", "finish", "share", "like", "bookmark", "read"]
    duration: Optional[int] = Field(None, ge=0, le=3600)


class HealthCheck(BaseModel):
    """헬스체크 응답"""
    status: str
    checks: Dict[str, bool]
    timestamp: datetime


class PersonalizedArticle(BaseModel):
    """개인화된 기사 응답"""
    title: str
    content: str
    key_points: List[str]
    reading_time: str
    disclaimer: Optional[str] = None
    cached: bool = False


# Structured Outputs 스키마
FACTS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "who": {"type": "array", "items": {"type": "string", "maxLength": 100}, "maxItems": 10},
        "what": {"type": "string", "maxLength": 200},
        "when": {"type": "string", "maxLength": 100},
        "where": {"type": "string", "maxLength": 100},
        "why": {"type": "string", "maxLength": 200},
        "how": {"type": "string", "maxLength": 200},
        "numbers": {"type": "object", "additionalProperties": {"type": "string", "maxLength": 50}},
        "quotes": {
            "type": "array",
            "maxItems": 5,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "speaker": {"type": "string", "maxLength": 100},
                    "content": {"type": "string", "maxLength": 200}
                },
                "required": ["speaker", "content"]
            }
        },
        "verified_facts": {"type": "array", "items": {"type": "string", "maxLength": 200}, "maxItems": 10}
    },
    "required": ["who", "what", "when", "where", "why", "how", "numbers", "quotes", "verified_facts"]
}

REWRITE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string", "maxLength": 200},
        "content": {"type": "string", "minLength": 2000, "maxLength": 8000},
        "key_points": {
            "type": "array",
            "items": {"type": "string", "maxLength": 100},
            "minItems": 3,
            "maxItems": 3
        },
        "reading_time": {
            "type": "string"
        },
        "disclaimer": {"type": "string", "maxLength": 300}
    },
    "required": ["title", "content", "key_points", "reading_time", "disclaimer"]
}