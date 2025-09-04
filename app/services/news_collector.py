"""
뉴스 수집기 (RSS 파싱 강건성 개선)
"""
import asyncio
import hashlib
from time import monotonic
from typing import List, Dict, Any
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

import aiohttp
import feedparser

from ..core.config import settings
from ..core.logging import get_logger, now_kst
from ..utils.helpers import clean_html_summary, validate_article_content, generate_article_id

logger = get_logger("news_collector")


class NewsCollector:
    """뉴스 수집기"""
    
    def __init__(self):
        self.sources = [
            {
                'name': '연합뉴스', 
                'url': 'https://www.yonhapnewstv.co.kr/browse/feed/', 
                'category': 'general'
            },
            {
                'name': 'SBS뉴스',
                'url': 'https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=01',
                'category': 'general'
            },
            {
                'name': 'KBS뉴스', 
                'url': 'http://world.kbs.co.kr/rss/rss_news.htm?lang=k',
                'category': 'general'
            },
            {
                'name': 'MBC뉴스',
                'url': 'https://imnews.imbc.com/rss/news/news_00.xml', 
                'category': 'general'
            }
        ]
        self.session_timeout = aiohttp.ClientTimeout(total=settings.collect_timeout)
    
    async def _fetch_feed(self, session: aiohttp.ClientSession, source: Dict[str, str]) -> List[Dict[str, Any]]:
        """단일 RSS 피드 가져오기 (강건성 개선)"""
        start_time = monotonic()
        source_name = source['name']
        
        try:
            async with session.get(source['url']) as response:
                response.raise_for_status()
                text = await response.text()
                feed = feedparser.parse(text)
                
                # bozo 피드 감지
                if getattr(feed, "bozo", False):
                    bozo_err = getattr(feed, "bozo_exception", None)
                    logger.warning("피드 파싱 경고", source=source_name, error=str(bozo_err)[:200])
                
                if not feed.entries:
                    logger.warning("피드 항목 없음", source=source_name)
                    return []
                
                articles = []
                for entry in feed.entries[:10]:  # 최대 10개 항목만 처리
                    article = await self._process_entry(entry, source)
                    if article and validate_article_content(article):
                        articles.append(article)
                
                elapsed = monotonic() - start_time
                
                if len(articles) == 0:
                    logger.warning("피드 수집 0건", source=source_name, duration=round(elapsed, 2))
                else:
                    logger.info("피드 수집 성공", 
                               source=source_name, 
                               count=len(articles), 
                               duration=round(elapsed, 2))
                
                return articles
                
        except asyncio.TimeoutError:
            logger.error("피드 수집 타임아웃", source=source_name)
            return []
        except Exception as e:
            logger.error("피드 수집 실패", source=source_name, error=str(e)[:200])
            return []
    
    async def _process_entry(self, entry, source: Dict[str, str]) -> Dict[str, Any]:
        """RSS 엔트리를 기사 데이터로 변환"""
        # URL 추출
        url = getattr(entry, 'link', '')
        if not url:
            return None
        
        # 제목 추출 및 정리
        raw_title = (
            getattr(entry, 'title', None) or 
            getattr(entry, 'summary', '')[:50] or 
            "(제목 없음)"
        )
        title = clean_html_summary(raw_title, limit=200)
        
        # 본문 추출 및 정리
        summary = (
            getattr(entry, 'summary', '') or
            (entry.content[0].value if getattr(entry, "content", None) else '') or
            getattr(entry, 'description', '') or
            ''
        )
        content = clean_html_summary(summary)
        
        # 최소 콘텐츠 길이 체크
        if len(content) < settings.min_content_len:
            logger.debug("콘텐츠 길이 부족", url=url[:50], length=len(content))
            return None
        
        # 날짜 파싱
        published = await self._parse_date(entry)
        
        # 고유 ID 생성
        article_id = generate_article_id(url, published)
        
        return {
            'id': article_id,
            'title': title,
            'content': content,
            'url': url,
            'source': source['name'],
            'category': source.get('category', 'general'),
            'published': published
        }
    
    async def _parse_date(self, entry) -> str:
        """RSS 엔트리에서 날짜 파싱"""
        pub_raw = getattr(entry, 'published', None) or getattr(entry, 'updated', None)
        
        try:
            if pub_raw:
                dt = parsedate_to_datetime(pub_raw)
                if dt:
                    if dt.tzinfo:
                        published = dt.astimezone(ZoneInfo("Asia/Seoul")).isoformat()
                    else:
                        published = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Asia/Seoul")).isoformat()
                else:
                    published = now_kst()
            else:
                published = now_kst()
        except Exception as e:
            logger.debug("날짜 파싱 실패", raw_date=str(pub_raw)[:50], error=str(e))
            published = now_kst()
        
        return published
    
    async def collect_news(self) -> List[Dict[str, Any]]:
        """모든 소스에서 뉴스 수집"""
        headers = {
            "User-Agent": f"kkalkalnews/{settings.app_version}",
            "Accept": "application/rss+xml, application/xml, text/xml"
        }
        
        async with aiohttp.ClientSession(
            headers=headers,
            timeout=self.session_timeout
        ) as session:
            
            # 모든 소스에서 병렬로 수집
            tasks = [self._fetch_feed(session, source) for source in self.sources]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 병합 및 예외 처리
            all_articles = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    source_name = self.sources[i]['name'] if i < len(self.sources) else "unknown"
                    logger.error("수집 태스크 실패", source=source_name, error=str(result)[:200])
                    continue
                all_articles.extend(result)
            
            # 중복 제거 (URL 기준 + DB 기존 기사 체크)
            from ..api.dependencies import get_database, get_mongo_database
            
            db = get_mongo_database() or get_database()
            seen_urls = set()
            unique_articles = []
            
            for article in all_articles:
                url = article['url']
                if url not in seen_urls:
                    # 데이터베이스에서 기존 기사 체크
                    if hasattr(db, 'get_article_by_url'):
                        existing = db.get_article_by_url(url)
                        if existing:
                            logger.debug("기존 기사 스킵", title=article.get('title', '')[:50])
                            continue
                    
                    seen_urls.add(url)
                    unique_articles.append(article)
            
            logger.info("뉴스 수집 완료", 
                       total_collected=len(all_articles),
                       unique_articles=len(unique_articles),
                       sources_count=len(self.sources))
            
            return unique_articles
    
    async def health_check(self) -> bool:
        """뉴스 수집기 상태 확인 (최적화: 네트워크 호출 없이 설정만 확인)"""
        try:
            # 도훈님 최적화: 실제 HTTP 요청 대신 소스 설정만 확인
            return len(self.sources) > 0 and all('url' in source for source in self.sources)
        except Exception:
            return False