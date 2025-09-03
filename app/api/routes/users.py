"""
사용자 관련 API 엔드포인트
"""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime

from ...models.schemas import UserProfileCreateRequest, UserProfile, ActivityLog
from ...api.dependencies import get_database, log_request_info
from ...models.database import Database
from ...core.logging import get_logger, now_kst

logger = get_logger("api.users")

router = APIRouter(prefix="/api/users", tags=["users"])


@router.post("/profiles")
async def create_user_profile(
    profile_request: UserProfileCreateRequest,
    db: Database = Depends(get_database),
    request_info: Dict[str, str] = Depends(log_request_info)
):
    """사용자 프로필 생성"""
    
    logger.info("프로필 생성 요청", 
               user_id=profile_request.user_id[:10],
               **request_info)
    
    try:
        # 기존 프로필 확인
        existing_profile = db.get_user_profile(profile_request.user_id)
        
        now = now_kst()
        
        # UserProfile 데이터클래스 생성
        profile = UserProfile(
            user_id=profile_request.user_id,
            age=profile_request.age,
            gender=profile_request.gender,
            location=profile_request.location,
            job_categories=profile_request.job_categories,
            interests_finance=profile_request.interests_finance,
            interests_lifestyle=profile_request.interests_lifestyle,
            interests_hobby=profile_request.interests_hobby,
            interests_tech=profile_request.interests_tech,
            work_style=profile_request.work_style,
            family_status=profile_request.family_status,
            living_situation=profile_request.living_situation,
            reading_mode=profile_request.reading_mode,
            created_at=existing_profile.created_at if existing_profile else now,
            updated_at=now
        )
        
        # 프로필 저장
        db.save_user_profile(profile)
        
        action = "updated" if existing_profile else "created"
        logger.info(f"프로필 {action}", user_id=profile_request.user_id[:10])
        
        return {
            "message": f"프로필이 {action} 되었습니다",
            "user_id": profile_request.user_id,
            "action": action
        }
        
    except Exception as e:
        logger.error("프로필 생성 실패", 
                    error=str(e),
                    user_id=profile_request.user_id[:10])
        raise HTTPException(status_code=500, detail="프로필 생성 중 오류가 발생했습니다")


@router.get("/profiles/{user_id}")
async def get_user_profile(
    user_id: str,
    db: Database = Depends(get_database),
    request_info: Dict[str, str] = Depends(log_request_info)
):
    """사용자 프로필 조회"""
    
    logger.debug("프로필 조회 요청", user_id=user_id[:10], **request_info)
    
    try:
        profile = db.get_user_profile(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="사용자 프로필을 찾을 수 없습니다")
        
        logger.debug("프로필 조회 성공", user_id=user_id[:10])
        
        return {
            "user_id": profile.user_id,
            "age": profile.age,
            "gender": profile.gender,
            "location": profile.location,
            "job_categories": profile.job_categories,
            "interests": {
                "finance": profile.interests_finance,
                "lifestyle": profile.interests_lifestyle,
                "hobby": profile.interests_hobby,
                "tech": profile.interests_tech
            },
            "work_style": profile.work_style,
            "family_status": profile.family_status,
            "living_situation": profile.living_situation,
            "reading_mode": profile.reading_mode,
            "created_at": profile.created_at,
            "updated_at": profile.updated_at
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("프로필 조회 실패", error=str(e), user_id=user_id[:10])
        raise HTTPException(status_code=500, detail="프로필을 가져올 수 없습니다")


@router.post("/activity")
async def log_user_activity(
    activity: ActivityLog,
    db: Database = Depends(get_database),
    request_info: Dict[str, str] = Depends(log_request_info)
):
    """사용자 활동 로깅"""
    
    logger.debug("활동 로그 요청",
                user_id=activity.user_id[:10],
                article_id=activity.article_id,
                action=activity.action,
                **request_info)
    
    try:
        # 활동 로그 저장
        db.log_activity(
            user_id=activity.user_id,
            article_id=activity.article_id,
            action=activity.action,
            duration=activity.duration
        )
        
        logger.debug("활동 로그 저장 완료",
                    user_id=activity.user_id[:10],
                    action=activity.action)
        
        return {
            "message": "활동이 기록되었습니다",
            "action": activity.action
        }
        
    except Exception as e:
        logger.error("활동 로그 실패", 
                    error=str(e),
                    user_id=activity.user_id[:10])
        raise HTTPException(status_code=500, detail="활동 기록 중 오류가 발생했습니다")


@router.get("/activity/{user_id}")
async def get_user_activity(
    user_id: str,
    limit: int = 20,
    db: Database = Depends(get_database),
    request_info: Dict[str, str] = Depends(log_request_info)
):
    """사용자 활동 히스토리 조회"""
    
    if limit > 100:
        limit = 100  # 최대 100개로 제한
    
    logger.debug("활동 히스토리 요청", 
                user_id=user_id[:10], 
                limit=limit, 
                **request_info)
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT article_id, action, duration, created_at
                FROM user_activity
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (user_id, limit))
            
            activities = []
            for row in cursor.fetchall():
                activities.append({
                    "article_id": row['article_id'],
                    "action": row['action'],
                    "duration": row['duration'],
                    "created_at": row['created_at']
                })
        
        logger.debug("활동 히스토리 응답", 
                    user_id=user_id[:10], 
                    count=len(activities))
        
        return {
            "user_id": user_id,
            "activities": activities,
            "count": len(activities)
        }
        
    except Exception as e:
        logger.error("활동 히스토리 조회 실패", 
                    error=str(e), 
                    user_id=user_id[:10])
        raise HTTPException(status_code=500, detail="활동 히스토리를 가져올 수 없습니다")