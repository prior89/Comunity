"""
뉴스 처리 파이프라인 (분산 락 지원)
"""
import asyncio
import uuid
import hashlib
from time import monotonic
from typing import Dict, Any, Optional
from dataclasses import asdict

from ..models.database import Database
from ..models.schemas import UserProfile, ExtractedFacts
from ..services.ai_engine import AIEngine
from ..services.news_collector import NewsCollector
from ..core.config import settings
from ..core.logging import get_logger
from ..core.security import profile_hash
# from ..utils.cache import cache_manager  # 캐시 완전 제거

logger = get_logger("news_processor")


class DistributedLock:
    """분산 락 (캐시 제거됨)"""
    
    def __init__(self, database: Database):
        self.db = database
        self.redis_available = False  # 캐시 완전 제거
    
    async def acquire(self, lock_name: str, holder: str, ttl: int = 180) -> bool:
        """분산 락 획득"""
        if self.redis_available:
            try:
                # Redis 기반 락
                lock_key = f"lock:{lock_name}"
                # Redis 제거됨
                acquired = False  # await cache_manager.redis_client.set(
                    # lock_key, holder, nx=True, ex=ttl
                # )
                if acquired:
                    logger.debug("Redis 락 획득", lock=lock_name, holder=holder[:8])
                return bool(acquired)
            except Exception as e:
                logger.warning("Redis 락 실패, SQLite 폴백", error=str(e))
        
        # SQLite fallback
        return self._sqlite_acquire_lock(lock_name, holder, ttl)
    
    async def update_heartbeat(self, lock_name: str, holder: str) -> bool:
        """락 하트비트 업데이트"""
        if self.redis_available:
            try:
                lock_key = f"lock:{lock_name}"
                # 현재 홀더 확인 후 TTL 갱신
                current_holder = None  # await cache_manager.redis_client.get(lock_key)
                if current_holder == holder:
                    # await cache_manager.redis_client.expire(lock_key, settings.collect_lock_ttl)
                    return True
                return False
            except Exception:
                pass
        
        # SQLite fallback
        return self._sqlite_update_heartbeat(lock_name, holder)
    
    async def release(self, lock_name: str, holder: str) -> None:
        """락 해제"""
        if self.redis_available:
            try:
                lock_key = f"lock:{lock_name}"
                # Lua 스크립트로 원자적 삭제
                lua_script = """
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    return redis.call("del", KEYS[1])
                else
                    return 0
                end
                """
                # await cache_manager.redis_client.eval(lua_script, 1, lock_key, holder)
                logger.debug("Redis 락 해제", lock=lock_name, holder=holder[:8])
                return
            except Exception:
                pass
        
        # SQLite fallback
        self._sqlite_release_lock(lock_name, holder)
    
    def _sqlite_acquire_lock(self, lock_name: str, holder: str, ttl: int) -> bool:
        """SQLite 기반 락 획득"""
        from datetime import datetime, timedelta
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cutoff = (datetime.now() - timedelta(seconds=ttl)).isoformat()
            
            try:
                # 기존 락이 만료되었거나 없으면 획득
                cursor.execute('''
                    INSERT INTO locks(name, holder, acquired_at) VALUES (?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        holder = excluded.holder,
                        acquired_at = excluded.acquired_at
                    WHERE locks.acquired_at < ?
                ''', (lock_name, holder, now, cutoff))
                
                # 현재 홀더 확인
                cursor.execute('SELECT holder FROM locks WHERE name = ?', (lock_name,))
                row = cursor.fetchone()
                return row and row['holder'] == holder
            except Exception:
                return False
    
    def _sqlite_update_heartbeat(self, lock_name: str, holder: str) -> bool:
        """SQLite 기반 하트비트 업데이트"""
        from datetime import datetime
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute('''
                UPDATE locks 
                SET acquired_at = ?
                WHERE name = ? AND holder = ?
            ''', (now, lock_name, holder))
            return cursor.rowcount > 0
    
    def _sqlite_release_lock(self, lock_name: str, holder: str) -> None:
        """SQLite 기반 락 해제"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM locks WHERE name = ? AND holder = ?', 
                          (lock_name, holder))


class NewsProcessor:
    """뉴스 처리 파이프라인"""
    
    def __init__(self, api_key: str):
        self.db = Database()
        self.collector = NewsCollector()
        self.ai_engine = AIEngine(api_key)
        self.distributed_lock = DistributedLock(self.db)
        self._local_lock = asyncio.Lock()
        self._current_holder = None
    
    async def process_news_batch(self) -> bool:
        """뉴스 수집 및 처리 (분산 락 지원)"""
        holder = f"proc_{uuid.uuid4().hex[:8]}"
        
        # 분산 락 획득 시도
        if not await self.distributed_lock.acquire("news_collector", holder, settings.collect_lock_ttl):
            # 로컬 락 체크 (단일 프로세스 환경)
            if self._local_lock.locked():
                logger.info("수집 스킵: 로컬 프로세스에서 실행 중")
                return False
            
            logger.info("수집 스킵: 다른 노드에서 실행 중")
            return False
        
        self._current_holder = holder
        logger.info("뉴스 처리 배치 시작", holder=holder)
        
        try:
            async with self._local_lock:
                return await self._process_batch_internal(holder)
        finally:
            # 분산 락 해제
            if self._current_holder:
                await self.distributed_lock.release("news_collector", self._current_holder)
                self._current_holder = None
    
    async def _process_batch_internal(self, holder: str) -> bool:
        """내부 배치 처리 로직"""
        try:
            # 1. 뉴스 수집
            articles = await self.collector.collect_news()
            if not articles:
                logger.warning("수집된 기사가 없습니다")
                return True
            
            logger.info("뉴스 수집 완료", count=len(articles))
            
            # 2. 각 기사 처리
            processed = 0
            last_heartbeat = monotonic()
            
            for idx, article in enumerate(articles[:settings.articles_per_batch]):
                # 하트비트 업데이트 (주기적으로)
                now = monotonic()
                if idx > 0 and (idx % 2 == 0 or now - last_heartbeat > 30):
                    if not await self.distributed_lock.update_heartbeat("news_collector", holder):
                        logger.error("락 하트비트 실패, 처리 중단")
                        break
                    last_heartbeat = now
                
                try:
                    # URL 중복 체크
                    with self.db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT 1 FROM original_articles WHERE url = ?", (article['url'],))
                        if cursor.fetchone():
                            logger.debug("중복 기사 스킵", url=article['url'][:50])
                            continue
                    
                    # 기사 저장
                    if not self.db.save_article(article):
                        logger.debug("기사 저장 스킵 (중복)", article_id=article['id'])
                        continue
                    
                    # 팩트 추출
                    facts = await self.ai_engine.extract_facts(article)
                    
                    # 팩트 저장
                    self.db.save_facts(article['id'], facts)
                    
                    processed += 1
                    logger.info("기사 처리 완료", 
                               processed=processed, 
                               title=article['title'][:30])
                    
                except Exception as e:
                    logger.error("기사 처리 실패", 
                                error=str(e), 
                                article_id=article.get('id'))
                    continue
            
            logger.info("배치 처리 완료", processed=processed, total=len(articles))
            return True
            
        except Exception as e:
            logger.error("배치 처리 실패", error=str(e))
            return False
    
    async def generate_personalized(self, article_id: str, user_id: str) -> Dict[str, Any]:
        """개인화 콘텐츠 생성 (캐시 최적화)"""
        
        # 사용자 프로필 조회
        profile = self.db.get_user_profile(user_id)
        if not profile:
            raise ValueError("사용자 프로필을 찾을 수 없습니다")
        
        # 프로필 해시를 포함한 캐시 키 생성 (reading_mode 제거)
        profile_data = {
            "job_categories": profile.job_categories,
            "interests": (
                profile.interests_finance + profile.interests_lifestyle +
                profile.interests_hobby + profile.interests_tech
            )[:10],  # MAX_INTERESTS
            "age": profile.age,
            "updated_at": profile.updated_at
        }
        
        ph = profile_hash(profile_data)
        cache_key = f"{article_id}_{user_id}_{ph}"
        content_id = hashlib.blake2s(cache_key.encode(), digest_size=12).hexdigest()
        
        # 캐시 완전 비활성화 (테스트용)
        cached_content = None
        # if cached_content:
        
        # 팩트와 원본 기사 조회
        facts = self.db.get_facts(article_id)
        if not facts:
            raise ValueError("팩트를 찾을 수 없습니다")
            
        # 원본 기사 제목 조회
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT title FROM original_articles WHERE id = ?', (article_id,))
            row = cursor.fetchone()
            original_title = row['title'] if row else facts.what
        
        # 원본 ai_engine으로 되돌림 (정확한 구현)
        personalized = await self.ai_engine.rewrite_for_user(facts, profile, original_title)
        
        # 캐시 저장 비활성화
        # self.db.save_personalized_content(content_id, article_id, user_id, ph, personalized)
        
        logger.info("개인화 콘텐츠 생성 완료", 
                   cache_id=content_id, 
                   user_id=user_id[:10])
        
        personalized['cached'] = False
        
        # 캐시 저장 완전 비활성화 (테스트용)
        # self.db.save_personalized_content(content_id, article_id, user_id, ph, personalized)
        
        return personalized
    
    async def health_check(self) -> Dict[str, bool]:
        """전체 시스템 상태 확인"""
        checks = {
            "database": await self.db.health_check(),
            "ai_engine": await self.ai_engine.health_check(),
            "news_collector": await self.collector.health_check(),
            "cache": True  # 캐시 제거됨
        }
        
        logger.info("헬스체크 완료", checks=checks)
        return checks