"""
뉴스 관련 API 엔드포인트
"""
import json
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request, Response
from fastapi.responses import JSONResponse

from ...models.schemas import PersonalizeRequest, PersonalizedArticle
from ...api.dependencies import get_news_processor, verify_internal_key, log_request_info
from ...services.news_processor import NewsProcessor
from ...core.logging import get_logger
from ...utils.helpers import make_etag, apply_cache_headers

logger = get_logger("api.news")

router = APIRouter(prefix="/api/news", tags=["news"])


@router.post("/refresh")
async def refresh_news(
    background_tasks: BackgroundTasks,
    request: Request,
    force: bool = False,
    _: bool = Depends(verify_internal_key),
    processor: NewsProcessor = Depends(get_news_processor),
    request_info: Dict[str, str] = Depends(log_request_info)
):
    """뉴스 수집 및 처리 (백그라운드)"""
    
    logger.info("뉴스 갱신 요청", force=force, **request_info)
    
    # force=True일 때 분산 락 무시하고 강제 실행
    if force:
        try:
            logger.info("강제 수집: 분산 락 무시하고 즉시 실행")
            
            # 즉시 실행 (force=True 전달)
            result = await processor.process_news_batch(force=True)
            return {
                "message": "뉴스 갱신이 강제로 완료되었습니다",
                "status": "completed", 
                "result": result
            }
        except Exception as e:
            logger.error(f"강제 수집 실패: {e}")
            return {
                "message": f"강제 수집 실패: {e}",
                "status": "error"
            }
    
    # 일반 백그라운드 처리 (force 파라미터 전달)
    background_tasks.add_task(processor.process_news_batch, force)
    
    return {
        "message": "뉴스 갱신이 백그라운드에서 시작되었습니다",
        "status": "processing"
    }


@router.post("/test")
async def test_endpoint():
    """테스트용 단순 엔드포인트"""
    return {"message": "테스트 성공", "status": "ok"}

@router.post("/personalize")
async def personalize_article(
    personalize_request: PersonalizeRequest,
    request: Request,
    processor: NewsProcessor = Depends(get_news_processor),
    request_info: Dict[str, str] = Depends(log_request_info)
):
    """기사 개인화 (완전 방어형 - 절대 500 금지)"""
    
    logger.info("개인화 요청", 
               article_id=personalize_request.article_id, 
               user_id=personalize_request.user_id[:10],
               **request_info)
    
    try:
        logger.info("개인화 시작: processor.generate_personalized 호출")
        personalized = await processor.generate_personalized(
            personalize_request.article_id, 
            personalize_request.user_id
        )
        logger.info("개인화 성공: 응답 데이터 생성 완료")
        
        # 성공 시 정상 응답
        return {
            "ok": True,
            "provider": personalized.get("provider", "unknown"),
            "personalized_article": personalized.get("personalized_article") or personalized.get("content", ""),
            "title": personalized.get("title", ""),
            "key_points": personalized.get("key_points", []),
            "reading_time": personalized.get("reading_time", "2분"),
            "is_fallback": False
        }
        
    except Exception as e:
        logger.error("개인화 처리 실패", 
                    error=str(e),
                    article_id=personalize_request.article_id,
                    user_id=personalize_request.user_id[:10])
        
        # 도훈님 방어 패턴: 500 대신 200 + 스텁 응답
        print(f"[personalize] failed: {type(e).__name__} {e}")
        return {
            "ok": False,
            "provider": "stub",
            "personalized_article": f"개인화 처리 중 오류가 발생했습니다: {str(e)[:200]}",
            "title": "뉴스 기사",
            "key_points": ["처리 중 오류 발생"],
            "reading_time": "2분",
            "is_fallback": True
        }


@router.get("/articles")
async def get_articles(
    limit: int = 10,
    offset: int = 0,
    processor: NewsProcessor = Depends(get_news_processor),
    request_info: Dict[str, str] = Depends(log_request_info)
):
    """최신 기사 목록 조회"""
    
    if limit > 50:
        limit = 50  # 최대 50개로 제한
    
    logger.debug("기사 목록 요청", limit=limit, offset=offset, **request_info)
    
    try:
        with processor.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, title, source, published, collected_at
                FROM original_articles
                ORDER BY collected_at DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            
            articles = []
            for row in cursor.fetchall():
                articles.append({
                    "id": row['id'],
                    "title": row['title'],
                    "source": row['source'],
                    "published": row['published'],
                    "collected_at": row['collected_at']
                })
        
        logger.debug("기사 목록 응답", count=len(articles))
        return {"articles": articles, "count": len(articles)}
        
    except Exception as e:
        logger.error("기사 목록 조회 실패", error=str(e))
        raise HTTPException(status_code=500, detail="기사 목록을 가져올 수 없습니다")


@router.get("/articles/{article_id}")
async def get_article(
    article_id: str,
    processor: NewsProcessor = Depends(get_news_processor),
    request_info: Dict[str, str] = Depends(log_request_info)
):
    """특정 기사 상세 조회"""
    
    logger.debug("기사 상세 요청", article_id=article_id, **request_info)
    
    try:
        import aiosqlite
        
        # 기사 정보 비동기 조회
        async with aiosqlite.connect(processor.db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await processor.db._configure_connection(conn)
            
            async with conn.execute('''
                SELECT * FROM original_articles WHERE id = ?
            ''', (article_id,)) as cursor:
                row = await cursor.fetchone()
                
                if not row:
                    raise HTTPException(status_code=404, detail="기사를 찾을 수 없습니다")
                
                article = {
                    "id": row['id'],
                    "title": row['title'],
                    "content": row['content'],
                    "source": row['source'],
                    "url": row['url'],
                    "published": row['published'],
                    "collected_at": row['collected_at']
                }
        
        # 팩트 정보도 함께 조회 (비동기)
        facts = await processor.db.get_facts(article_id)
        if facts:
            article["facts"] = {
                    "who": facts.who,
                    "what": facts.what,
                    "when": facts.when,
                    "where": facts.where,
                    "why": facts.why,
                    "how": facts.how,
                    "numbers": facts.numbers,
                    "quotes": facts.quotes,
                    "verified_facts": facts.verified_facts
                }
        
        logger.debug("기사 상세 응답", article_id=article_id)
        return article
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("기사 상세 조회 실패", error=str(e), article_id=article_id)
        raise HTTPException(status_code=500, detail="기사를 가져올 수 없습니다")