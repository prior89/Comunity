"""
데이터베이스 관리 (SQLite WAL 모드 최적화)
"""
import sqlite3
import json
import asyncio
from contextlib import contextmanager
from typing import Optional, Dict, Any
from dataclasses import asdict

from .schemas import UserProfile, ExtractedFacts
from ..core.config import settings
from ..core.logging import get_logger, now_kst

logger = get_logger("database")


class Database:
    """최적화된 SQLite 데이터베이스 클래스"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or "kkalkalnews.db"
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        """최적화된 데이터베이스 연결"""
        conn = sqlite3.connect(
            self.db_path, 
            check_same_thread=False,
            isolation_level=None  # autocommit 모드
        )
        conn.row_factory = sqlite3.Row
        
        # 2025년 검증된 SQLite WAL 최적화 설정
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")  # WAL과 함께 사용시 안전
        conn.execute("PRAGMA cache_size=-64000;")   # 64MB 캐시
        conn.execute("PRAGMA temp_store=MEMORY;")   # 임시 데이터 메모리 저장
        conn.execute("PRAGMA mmap_size=268435456;") # 256MB 메모리 맵
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA wal_autocheckpoint=1000;")
        conn.execute("PRAGMA journal_size_limit=104857600;")  # 100MB 상한
        conn.execute("PRAGMA optimize;")  # 자동 최적화
        
        try:
            yield conn
        finally:
            conn.close()
    
    def init_db(self):
        """데이터베이스 초기화"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 사용자 프로필 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    age INTEGER,
                    gender TEXT,
                    location TEXT,
                    job_categories TEXT,
                    interests_finance TEXT,
                    interests_lifestyle TEXT,
                    interests_hobby TEXT,
                    interests_tech TEXT,
                    work_style TEXT,
                    family_status TEXT,
                    living_situation TEXT,
                    reading_mode TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            ''')
            
            # 원본 기사 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS original_articles (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    content TEXT,
                    source TEXT,
                    url TEXT UNIQUE,
                    published TEXT,
                    collected_at TEXT
                )
            ''')
            
            # 추출된 팩트 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS extracted_facts (
                    article_id TEXT PRIMARY KEY,
                    facts_json TEXT,
                    extracted_at TEXT,
                    FOREIGN KEY (article_id) REFERENCES original_articles(id) ON DELETE CASCADE
                )
            ''')
            
            # 개인화 콘텐츠 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS personalized_content (
                    id TEXT PRIMARY KEY,
                    article_id TEXT,
                    user_id TEXT,
                    profile_hash TEXT,
                    title TEXT,
                    content TEXT,
                    key_points TEXT,
                    reading_time TEXT,
                    created_at TEXT,
                    FOREIGN KEY (article_id) REFERENCES original_articles(id) ON DELETE CASCADE
                )
            ''')
            
            # 사용자 활동 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    article_id TEXT,
                    action TEXT,
                    duration INTEGER,
                    created_at TEXT,
                    FOREIGN KEY (article_id) REFERENCES original_articles(id) ON DELETE CASCADE
                )
            ''')
            
            # 인덱스 생성
            indexes = [
                'CREATE INDEX IF NOT EXISTS idx_facts_article ON extracted_facts(article_id)',
                'CREATE INDEX IF NOT EXISTS idx_pc_article_user ON personalized_content(article_id, user_id, profile_hash)',
                'CREATE INDEX IF NOT EXISTS idx_activity_user ON user_activity(user_id, created_at)',
                'CREATE INDEX IF NOT EXISTS idx_articles_collected ON original_articles(collected_at DESC)',
                'CREATE INDEX IF NOT EXISTS idx_facts_extracted ON extracted_facts(extracted_at DESC)',
                'CREATE INDEX IF NOT EXISTS idx_pc_created ON personalized_content(created_at)',
                'CREATE INDEX IF NOT EXISTS idx_activity_created ON user_activity(created_at)'
            ]
            
            for index_sql in indexes:
                cursor.execute(index_sql)
        
        logger.info("데이터베이스 초기화 완료")
    
    def save_user_profile(self, profile: UserProfile) -> None:
        """사용자 프로필 저장"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_profiles(
                    user_id, age, gender, location, job_categories,
                    interests_finance, interests_lifestyle, interests_hobby, interests_tech,
                    work_style, family_status, living_situation, reading_mode,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                profile.user_id[:64],
                profile.age,
                profile.gender,
                profile.location[:100],
                json.dumps(profile.job_categories, ensure_ascii=False),
                json.dumps(profile.interests_finance, ensure_ascii=False),
                json.dumps(profile.interests_lifestyle, ensure_ascii=False),
                json.dumps(profile.interests_hobby, ensure_ascii=False),
                json.dumps(profile.interests_tech, ensure_ascii=False),
                profile.work_style,
                profile.family_status,
                profile.living_situation,
                profile.reading_mode,
                profile.created_at,
                profile.updated_at
            ))
        
        logger.info("프로필 저장 완료", user_id=profile.user_id[:10])
    
    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """사용자 프로필 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM user_profiles WHERE user_id = ?', (user_id[:64],))
            row = cursor.fetchone()
            
            if row:
                return UserProfile(
                    user_id=row['user_id'],
                    age=row['age'],
                    gender=row['gender'],
                    location=row['location'],
                    job_categories=json.loads(row['job_categories']),
                    interests_finance=json.loads(row['interests_finance']),
                    interests_lifestyle=json.loads(row['interests_lifestyle']),
                    interests_hobby=json.loads(row['interests_hobby']),
                    interests_tech=json.loads(row['interests_tech']),
                    work_style=row['work_style'],
                    family_status=row['family_status'],
                    living_situation=row['living_situation'],
                    reading_mode=row['reading_mode'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
            return None
    
    def save_article(self, article: Dict[str, Any]) -> bool:
        """기사 저장"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO original_articles
                    (id, title, content, source, url, published, collected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    article['id'],
                    article['title'],
                    article['content'],
                    article['source'],
                    article['url'],
                    article['published'],
                    now_kst()
                ))
                return cursor.rowcount > 0
            except Exception as e:
                logger.error("기사 저장 실패", error=str(e), article_id=article.get('id'))
                return False
    
    def save_facts(self, article_id: str, facts: ExtractedFacts) -> None:
        """팩트 저장"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO extracted_facts
                (article_id, facts_json, extracted_at)
                VALUES (?, ?, ?)
            ''', (
                article_id,
                json.dumps(asdict(facts), ensure_ascii=False),
                now_kst()
            ))
    
    def get_facts(self, article_id: str) -> Optional[ExtractedFacts]:
        """팩트 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT facts_json FROM extracted_facts WHERE article_id = ?', 
                (article_id,)
            )
            row = cursor.fetchone()
            
            if row:
                facts_dict = json.loads(row['facts_json'])
                return ExtractedFacts(**facts_dict)
            return None
    
    def save_personalized_content(self, content_id: str, article_id: str, 
                                 user_id: str, profile_hash: str, 
                                 personalized: Dict[str, Any]) -> None:
        """개인화 콘텐츠 저장"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO personalized_content
                (id, article_id, user_id, profile_hash, title, content, key_points, reading_time, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                content_id,
                article_id,
                user_id,
                profile_hash,
                personalized['title'],
                personalized['content'],
                json.dumps(personalized['key_points'], ensure_ascii=False),
                personalized['reading_time'],
                now_kst()
            ))
    
    def get_personalized_content(self, content_id: str) -> Optional[Dict[str, Any]]:
        """개인화 콘텐츠 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM personalized_content WHERE id = ?', 
                (content_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return {
                    "title": row['title'],
                    "content": row['content'],
                    "key_points": json.loads(row['key_points']),
                    "reading_time": row['reading_time'],
                    "cached": True
                }
            return None
    
    def log_activity(self, user_id: str, article_id: str, action: str, duration: Optional[int] = None) -> None:
        """사용자 활동 로깅"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_activity (user_id, article_id, action, duration, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, article_id, action, duration, now_kst()))
    
    def cleanup_old_data(self) -> Dict[str, int]:
        """오래된 데이터 정리"""
        from datetime import datetime, timedelta
        
        cutoff_pc = (datetime.now() - timedelta(days=settings.pc_ttl_days)).isoformat()
        cutoff_activity = (datetime.now() - timedelta(days=settings.activity_ttl_days)).isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM personalized_content WHERE created_at < ?", (cutoff_pc,))
            pc_deleted = cursor.rowcount
            
            cursor.execute("DELETE FROM user_activity WHERE created_at < ?", (cutoff_activity,))
            activity_deleted = cursor.rowcount
            
            # WAL 체크포인트
            cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        
        return {"pc_deleted": pc_deleted, "activity_deleted": activity_deleted}
    
    async def health_check(self) -> bool:
        """데이터베이스 상태 확인"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error("데이터베이스 헬스체크 실패", error=str(e))
            return False