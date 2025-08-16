"""
뉴스 관련 API 엔드포인트
"""
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request

from ...models.schemas import PersonalizeRequest, PersonalizedArticle
from ...api.dependencies import get_news_processor, require_write_permission, log_request_info
from ...services.news_processor import NewsProcessor
from ...core.logging import get_logger

logger = get_logger("api.news")

router = APIRouter(prefix="/api/news", tags=["news"])


@router.post("/refresh")
async def refresh_news(
    background_tasks: BackgroundTasks,
    request: Request,
    _: None = Depends(require_write_permission),
    processor: NewsProcessor = Depends(get_news_processor),
    request_info: Dict[str, str] = Depends(log_request_info)
):
    """뉴스 수집 및 처리 (백그라운드)"""
    
    logger.info("뉴스 갱신 요청", **request_info)
    
    # 백그라운드에서 뉴스 처리
    background_tasks.add_task(processor.process_news_batch)
    
    return {
        "message": "뉴스 갱신이 백그라운드에서 시작되었습니다",
        "status": "processing"
    }


@router.post("/personalize", response_model=PersonalizedArticle)
async def personalize_article(
    request: PersonalizeRequest,
    processor: NewsProcessor = Depends(get_news_processor),
    request_info: Dict[str, str] = Depends(log_request_info)
):
    """기사 개인화"""
    
    logger.info("개인화 요청", 
               article_id=request.article_id, 
               user_id=request.user_id[:10],
               **request_info)
    
    try:
        personalized = await processor.generate_personalized(
            request.article_id, 
            request.user_id
        )
        
        logger.info("개인화 완료", 
                   article_id=request.article_id,
                   user_id=request.user_id[:10],
                   cached=personalized.get('cached', False))
        
        return PersonalizedArticle(**personalized)
        
    except ValueError as e:
        logger.warning("개인화 실패", 
                      error=str(e),
                      article_id=request.article_id,
                      user_id=request.user_id[:10])
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("개인화 처리 오류", 
                    error=str(e),
                    article_id=request.article_id,
                    user_id=request.user_id[:10])
        raise HTTPException(status_code=500, detail="개인화 처리 중 오류가 발생했습니다")


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
        with processor.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM original_articles WHERE id = ?
            ''', (article_id,))
            
            row = cursor.fetchone()
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
            
            # 팩트 정보도 함께 조회
            facts = processor.db.get_facts(article_id)
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