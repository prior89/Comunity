"""
멀티모달 사용자 데이터 스키마
"""
from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class MultimodalPreference(BaseModel):
    """멀티모달 선호도"""
    user_id: str
    
    # 시각적 요소 선호
    visual_preference: Literal["text_only", "with_images", "infographic", "charts", "diagrams"]
    image_style: Literal["realistic", "illustration", "minimal", "detailed"]
    
    # 오디오 선호
    audio_preference: Literal["no_audio", "voice_narration", "background_music", "sound_effects"]
    voice_style: Literal["professional", "friendly", "calm", "energetic"]
    
    # 영상 선호  
    video_preference: Literal["no_video", "animations", "live_action", "screen_recordings"]
    video_length: Literal["short", "medium", "long"]  # 30초, 2분, 5분+
    
    # 상호작용 선호
    interaction_preference: Literal["static", "interactive", "vr_ready", "ar_ready"]
    
    # 레이아웃 선호
    layout_preference: Literal["text_focused", "media_rich", "balanced", "minimal"]
    
    created_at: str
    updated_at: str


class MediaFeedback(BaseModel):
    """멀티미디어 콘텐츠 피드백"""
    user_id: str
    content_id: str
    
    # 요소별 만족도 (1-5점)
    text_satisfaction: int = Field(ge=1, le=5)
    image_satisfaction: Optional[int] = Field(None, ge=1, le=5)
    audio_satisfaction: Optional[int] = Field(None, ge=1, le=5)
    video_satisfaction: Optional[int] = Field(None, ge=1, le=5)
    
    # 전체 만족도
    overall_satisfaction: int = Field(ge=1, le=5)
    
    # 선호 요소
    preferred_elements: List[Literal["text", "image", "audio", "video", "charts"]]
    
    # 개선 요청
    improvement_requests: List[str] = Field(default_factory=list)
    
    created_at: str


class SwipeData(BaseModel):
    """틴더식 스와이프 데이터"""
    user_id: str
    
    # 스와이프 대상
    content_type: Literal["news_category", "visual_style", "audio_style", "layout_type"]
    content_item: str  # 실제 선택지
    
    # 스와이프 결과
    action: Literal["like", "dislike", "super_like", "skip"]
    
    # 스와이프 메타데이터 (특허 활용)
    swipe_time: float  # 결정까지 걸린 시간
    swipe_speed: float  # 스와이프 속도
    swipe_direction: Literal["left", "right", "up", "down"]
    
    # 컨텍스트
    session_id: str
    device_type: Literal["mobile", "tablet", "desktop"]
    time_of_day: str
    
    created_at: str