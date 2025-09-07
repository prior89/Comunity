"""
MongoDB 연동을 위한 데이터베이스 클래스
"""
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
import json
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING

from .schemas import UserProfile, ExtractedFacts
from ..core.config import settings
from ..core.logging import get_logger, now_kst

logger = get_logger("mongodb")


class MongoDatabase:
    """MongoDB 비동기 데이터베이스 클래스"""
    
    def __init__(self, connection_string: str = None):
        self.connection_string = connection_string or settings.mongodb_uri or "mongodb://localhost:27017"
        self.database_name = "verachain-community"  # 코인 커뮤니티용 DB명
        self.client = None
        self.db = None
    
    async def connect(self):
        """MongoDB 연결"""
        try:
            self.client = AsyncIOMotorClient(self.connection_string)
            self.db = self.client[self.database_name]
            
            # 연결 테스트
            await self.client.admin.command('ping')
            
            # 인덱스 생성
            await self.create_indexes()
            
            logger.info("MongoDB 연결 성공", 
                       database=self.database_name)
            return True
            
        except Exception as e:
            logger.error("MongoDB 연결 실패", error=str(e))
            return False
    
    async def create_indexes(self):
        """코인 커뮤니티용 인덱스 생성"""
        try:
            # 사용자 컬렉션 인덱스
            await self.db.users.create_index([("id", ASCENDING)], unique=True)
            await self.db.users.create_index([("email", ASCENDING)], unique=True)
            await self.db.users.create_index([("nickname", ASCENDING)], unique=True)
            
            # 게시물 컬렉션 인덱스
            await self.db.posts.create_index([("id", ASCENDING)], unique=True)
            await self.db.posts.create_index([("author_id", ASCENDING)])
            await self.db.posts.create_index([("category", ASCENDING)])
            await self.db.posts.create_index([("created_at", DESCENDING)])
            await self.db.posts.create_index([("upvotes", DESCENDING)])
            
            # 댓글 컬렉션 인덱스
            await self.db.comments.create_index([("id", ASCENDING)], unique=True)
            await self.db.comments.create_index([("post_id", ASCENDING)])
            await self.db.comments.create_index([("author_id", ASCENDING)])
            
            # 채팅 메시지 인덱스
            await self.db.chat_messages.create_index([("id", ASCENDING)], unique=True)
            await self.db.chat_messages.create_index([("channel", ASCENDING)])
            await self.db.chat_messages.create_index([("created_at", DESCENDING)])
            
            # 분석 이벤트 인덱스
            await self.db.analytics_events.create_index([("event_id", ASCENDING)], unique=True)
            await self.db.analytics_events.create_index([("user_id", ASCENDING)])
            await self.db.analytics_events.create_index([("created_at", DESCENDING)])
            
            logger.info("VeraChain 코인 커뮤니티 인덱스 생성 완료")
            
        except Exception as e:
            logger.error("인덱스 생성 실패", error=str(e))
    
    async def close(self):
        """연결 종료"""
        if self.client:
            self.client.close()
            logger.info("MongoDB 연결 종료")
    
    # 기사 관련 메서드
    async def save_article(self, article: Dict[str, Any]) -> bool:
        """기사 저장"""
        try:
            article["_updated_at"] = datetime.utcnow()
            
            result = await self.db.articles.update_one(
                {"id": article["id"]},
                {"$set": article},
                upsert=True
            )
            
            logger.debug("기사 저장", article_id=article["id"])
            return True
            
        except Exception as e:
            logger.error("기사 저장 실패", error=str(e))
            return False
    
    async def get_articles(self, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """기사 목록 조회"""
        try:
            cursor = self.db.articles.find().sort("collected_at", DESCENDING).skip(offset).limit(limit)
            articles = await cursor.to_list(length=limit)
            
            # ObjectId 제거
            for article in articles:
                if "_id" in article:
                    del article["_id"]
            
            return articles
            
        except Exception as e:
            logger.error("기사 조회 실패", error=str(e))
            return []
    
    async def get_article_by_id(self, article_id: str) -> Optional[Dict[str, Any]]:
        """특정 기사 조회"""
        try:
            article = await self.db.articles.find_one({"id": article_id})
            if article and "_id" in article:
                del article["_id"]
            return article
            
        except Exception as e:
            logger.error("기사 조회 실패", article_id=article_id, error=str(e))
            return None
    
    # 사용자 프로필 관련 메서드
    async def save_user_profile(self, profile: UserProfile) -> bool:
        """사용자 프로필 저장"""
        try:
            profile_dict = {
                "user_id": profile.user_id,
                "age": profile.age,
                "gender": profile.gender,
                "location": profile.location,
                "job_categories": profile.job_categories,
                "interests_finance": profile.interests_finance,
                "interests_lifestyle": profile.interests_lifestyle,
                "interests_hobby": profile.interests_hobby,
                "interests_tech": profile.interests_tech,
                "work_style": profile.work_style,
                "family_status": profile.family_status,
                "living_situation": profile.living_situation,
                "reading_mode": profile.reading_mode,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            result = await self.db.user_profiles.update_one(
                {"user_id": profile.user_id},
                {"$set": profile_dict},
                upsert=True
            )
            
            logger.info("사용자 프로필 저장", user_id=profile.user_id)
            return True
            
        except Exception as e:
            logger.error("프로필 저장 실패", error=str(e))
            return False
    
    async def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """사용자 프로필 조회"""
        try:
            profile_dict = await self.db.user_profiles.find_one({"user_id": user_id})
            if not profile_dict:
                return None
            
            # ObjectId 제거
            if "_id" in profile_dict:
                del profile_dict["_id"]
            
            # 날짜 필드 제거 (UserProfile 스키마에 없음)
            for field in ["created_at", "updated_at"]:
                if field in profile_dict:
                    del profile_dict[field]
            
            return UserProfile(**profile_dict)
            
        except Exception as e:
            logger.error("프로필 조회 실패", user_id=user_id, error=str(e))
            return None
    
    # 사용자 활동 로깅
    async def log_user_activity(self, user_id: str, article_id: str, 
                               action: str, duration: Optional[int] = None) -> bool:
        """사용자 활동 로깅"""
        try:
            activity = {
                "user_id": user_id,
                "article_id": article_id,
                "action": action,
                "duration": duration,
                "timestamp": datetime.utcnow()
            }
            
            await self.db.user_activity.insert_one(activity)
            logger.debug("사용자 활동 로깅", user_id=user_id, action=action)
            return True
            
        except Exception as e:
            logger.error("활동 로깅 실패", error=str(e))
            return False
    
    # 개인화 캐시
    async def get_personalization_cache(self, article_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """개인화 캐시 조회"""
        try:
            cache = await self.db.personalization_cache.find_one({
                "article_id": article_id,
                "user_id": user_id
            })
            
            if cache and "_id" in cache:
                del cache["_id"]
            
            return cache
            
        except Exception as e:
            logger.error("캐시 조회 실패", error=str(e))
            return None
    
    async def save_personalization_cache(self, article_id: str, user_id: str, 
                                       personalized_content: Dict[str, Any]) -> bool:
        """개인화 캐시 저장"""
        try:
            cache_data = {
                "article_id": article_id,
                "user_id": user_id,
                "content": personalized_content,
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow()  # 만료 시간 설정 가능
            }
            
            await self.db.personalization_cache.update_one(
                {"article_id": article_id, "user_id": user_id},
                {"$set": cache_data},
                upsert=True
            )
            
            return True
            
        except Exception as e:
            logger.error("캐시 저장 실패", error=str(e))
            return False
    
    # 헬스체크
    async def health_check(self) -> bool:
        """데이터베이스 상태 확인"""
        try:
            await self.client.admin.command('ping')
            return True
        except:
            return False
    
    # 데이터 정리
    async def cleanup_old_data(self, days: int = 30) -> Dict[str, int]:
        """오래된 데이터 정리"""
        try:
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # 오래된 개인화 캐시 삭제
            pc_result = await self.db.personalization_cache.delete_many({
                "created_at": {"$lt": cutoff_date}
            })
            
            # 오래된 활동 로그 삭제 (옵션)
            activity_result = await self.db.user_activity.delete_many({
                "timestamp": {"$lt": cutoff_date}
            })
            
            logger.info("데이터 정리 완료", 
                       cache_deleted=pc_result.deleted_count,
                       activity_deleted=activity_result.deleted_count)
            
            return {
                "pc_deleted": pc_result.deleted_count,
                "activity_deleted": activity_result.deleted_count
            }
            
        except Exception as e:
            logger.error("데이터 정리 실패", error=str(e))
            return {"pc_deleted": 0, "activity_deleted": 0}