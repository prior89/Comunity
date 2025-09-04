"""
AI 뉴스 개인화 플랫폼 메인 애플리케이션 (v3.0.8)
모듈화된 아키텍처 + 2025년 최적화 적용
"""
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.models.database import Database
from app.services.news_processor import NewsProcessor
from app.api.dependencies import set_news_processor, set_database, set_mongo_database
from app.api.routes import news, users, system
from app.middleware import RateLimitMiddleware, RequestLoggingMiddleware
# from app.utils.cache import cache_manager  # 캐시 완전 제거

# 로깅 초기화
setup_logging()
logger = get_logger("main")

# 전역 변수
processor: NewsProcessor = None
database: Database = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 라이프사이클 관리"""
    global processor, database
    
    # 시작 시 초기화
    logger.info("애플리케이션 시작", 
               version=settings.app_version,
               environment=settings.environment)
    
    # 환경 검증
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY 환경변수가 필요합니다")
    
    if settings.environment == "production" and not settings.internal_api_key:
        raise RuntimeError("프로덕션 환경에서는 INTERNAL_API_KEY가 필요합니다")
    
    # 데이터베이스 초기화 (안전한 SQLite 우선)
    try:
        if settings.use_mongodb and settings.mongodb_uri:
            from app.models.mongodb import MongoDatabase
            mongodb = MongoDatabase(settings.mongodb_uri)
            mongo_connected = await mongodb.connect()
            
            if mongo_connected:
                set_mongo_database(mongodb)
                logger.info("MongoDB Atlas 연결 완료", cluster="verachain")
            else:
                raise Exception("MongoDB 연결 실패")
        else:
            raise Exception("MongoDB 설정 없음")
            
    except Exception as e:
        logger.warning(f"MongoDB 연결 실패, SQLite 사용: {e}")
        database = Database()
        set_database(database)
    
    # 뉴스 프로세서 초기화
    processor = NewsProcessor(settings.openai_api_key)
    set_news_processor(processor)
    
    # 시스템 상태 확인
    health_checks = await processor.health_check()
    logger.info("시스템 초기화 완료", health_checks=health_checks)
    
    # 백그라운드 작업 시작
    cleanup_task = asyncio.create_task(periodic_cleanup())
    initial_collection_task = asyncio.create_task(initial_news_collection())
    
    logger.info("서비스 준비 완료",
               features={
                   "structured_outputs": settings.use_structured_outputs,
                   "redis_cache": False,  # 캐시 완전 제거
                   "rate_limiting": True,
                   "distributed_locks": True
               })
    
    yield
    
    # 종료 시 정리
    logger.info("애플리케이션 종료 중...")
    
    # 백그라운드 작업 취소
    cleanup_task.cancel()
    initial_collection_task.cancel()
    
    # 진행 중인 작업들 정리
    try:
        await asyncio.wait_for(
            asyncio.gather(cleanup_task, initial_collection_task, return_exceptions=True),
            timeout=5.0
        )
    except asyncio.TimeoutError:
        logger.warning("백그라운드 작업 정리 타임아웃")
    
    logger.info("애플리케이션 종료 완료")


async def initial_news_collection():
    """초기 뉴스 수집"""
    try:
        await asyncio.sleep(2)  # 시작 지연
        await processor.process_news_batch()
        logger.info("초기 뉴스 수집 완료")
    except Exception as e:
        logger.error("초기 뉴스 수집 실패", error=str(e))


async def periodic_cleanup():
    """주기적 데이터 정리"""
    while True:
        try:
            # 24시간마다 정리
            await asyncio.sleep(24 * 3600)
            
            result = database.cleanup_old_data()
            logger.info("주기적 데이터 정리 완료",
                       pc_deleted=result["pc_deleted"],
                       activity_deleted=result["activity_deleted"])
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("주기적 데이터 정리 실패", error=str(e))


# FastAPI 앱 생성
app = FastAPI(
    title=settings.app_name,
    description="AI 기반 완전 맞춤형 뉴스 플랫폼 (모듈화된 아키텍처)",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None
)

# CORS 설정
if settings.cors_origins_list == ["*"]:
    logger.warning("CORS 와일드카드 사용 중 - 프로덕션에서는 특정 도메인 설정 권장")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-Request-ID", "If-None-Match", "If-Modified-Since"],
        expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining", "ETag", "Last-Modified", "Cache-Control"]
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-Request-ID", "If-None-Match", "If-Modified-Since"],
        expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining", "ETag", "Last-Modified", "Cache-Control"],
        max_age=3600
    )

# 미들웨어 추가 (순서 중요)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware, 
                  capacity=60, 
                  refill_rate=20)

# 라우터 등록
app.include_router(news.router)
app.include_router(users.router)
app.include_router(system.router)

# --- 투자자용 랜딩/상태 라우트 ---
from fastapi.responses import HTMLResponse, JSONResponse, Response
from datetime import datetime

SERVICE_NAME = "AI 뉴스 개인화 플랫폼"
SERVICE_VERSION = settings.app_version
ENVIRONMENT = settings.environment
STARTED_AT = datetime.utcnow()

@app.get("/status", response_class=JSONResponse)
def status_json():
    uptime = (datetime.utcnow() - STARTED_AT).total_seconds()
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "status": "running",
        "environment": ENVIRONMENT,
        "uptime_seconds": int(uptime),
        "docs": "disabled",
    }

@app.head("/")
def head_ok():
    return Response(status_code=200)

@app.get("/", response_class=HTMLResponse)
def landing():
    # public/index.html 파일을 직접 읽어서 반환
    try:
        import os
        html_path = os.path.join(os.path.dirname(__file__), "public", "index.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(html_content)
    except FileNotFoundError:
        # fallback HTML
        return HTMLResponse(f"""
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{SERVICE_NAME} · v{SERVICE_VERSION}</title>
  <meta name="description" content="AI 기반 뉴스 개인화 엔진 API" />
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    .badge {{ @apply inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium; }}
  </style>
</head>
<body class="bg-slate-950 text-slate-100">
  <div class="min-h-screen flex flex-col">
    <header class="border-b border-slate-800/70">
      <div class="mx-auto max-w-5xl px-6 py-5 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="h-8 w-8 rounded-xl bg-gradient-to-br from-emerald-400 to-cyan-500"></div>
          <h1 class="text-lg font-semibold">{SERVICE_NAME}</h1>
          <span class="badge bg-slate-800 text-slate-300">v{SERVICE_VERSION}</span>
          <span class="badge bg-emerald-900/40 text-emerald-300">{ENVIRONMENT}</span>
        </div>
        <a class="text-sm text-slate-300 hover:text-white underline underline-offset-4" href="/status">JSON Status</a>
      </div>
    </header>

    <main class="flex-1">
      <section class="mx-auto max-w-5xl px-6 py-10">
        <h2 class="text-3xl md:text-4xl font-bold tracking-tight">
          뉴스를 <span class="text-emerald-400">개인 맞춤형</span>으로 변환하는 AI
        </h2>
        <p class="mt-3 text-slate-300">
          팩트 추출 → 사용자 분석 → 맞춤형 재구성까지 2초에 완성.
          <span class="text-slate-200">특허 기술</span> 기반 개인화 엔진입니다.
        </p>

        <div class="mt-8 grid md:grid-cols-3 gap-4">
          <div class="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
            <div class="text-sm text-slate-400">Uptime</div>
            <div id="uptime" class="mt-1 text-xl font-semibold">—</div>
          </div>
          <div class="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
            <div class="text-sm text-slate-400">Health</div>
            <div id="health" class="mt-1 text-xl font-semibold">—</div>
            <div id="healthDetail" class="mt-1 text-xs text-slate-400"></div>
          </div>
          <div class="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
            <div class="text-sm text-slate-400">Endpoints</div>
            <ul class="mt-1 space-y-1 text-sm">
              <li><a class="text-emerald-300 hover:underline" href="/api/system/health">/api/system/health</a></li>
              <li><a class="text-emerald-300 hover:underline" href="/status">/status</a></li>
            </ul>
          </div>
        </div>

        <div class="mt-10 grid md:grid-cols-3 gap-4">
          <div class="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
            <div class="text-slate-200 font-semibold">AI 팩트 추출</div>
            <p class="mt-1 text-sm text-slate-400">5W1H 구조화, 수치 데이터 분석, 인용문 정리.</p>
          </div>
          <div class="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
            <div class="text-slate-200 font-semibold">개인화 엔진</div>
            <p class="mt-1 text-sm text-slate-400">사용자 프로필 기반 맞춤형 콘텐츠 재구성.</p>
          </div>
          <div class="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
            <div class="text-slate-200 font-semibold">클라우드 인프라</div>
            <p class="mt-1 text-sm text-slate-400">MongoDB Atlas 연동, 확장 가능한 아키텍처.</p>
          </div>
        </div>

        <div class="mt-10 rounded-2xl border border-emerald-800/30 bg-emerald-950/20 p-6">
          <div class="flex items-center gap-2">
            <div class="h-2 w-2 rounded-full bg-emerald-400"></div>
            <span class="text-sm font-semibold text-emerald-300">특허 기술</span>
          </div>
          <h3 class="mt-2 text-lg font-semibold">다차원 사용자 프로필 분석 기반 동적 콘텐츠 변환</h3>
          <p class="mt-1 text-sm text-slate-300">
            정부 우선심사 통과. AI 기반 개인화 기술로 동일한 뉴스를 사용자별 맞춤 콘텐츠로 변환.
          </p>
        </div>

        <div class="mt-10 flex flex-wrap gap-3">
          <a href="/status" class="px-4 py-2 rounded-xl bg-emerald-500/90 hover:bg-emerald-500 text-slate-900 font-semibold">라이브 상태</a>
          <a href="/api/system/health" class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-100">헬스체크</a>
        </div>
      </section>
    </main>

    <footer class="border-t border-slate-800/70">
      <div class="mx-auto max-w-5xl px-6 py-6 text-sm text-slate-400">
        © {datetime.utcnow().year} AI 뉴스 개인화 플랫폼 · All rights reserved.
      </div>
    </footer>
  </div>

  <script>
    (async () => {{
      try {{
        const s = await fetch("/status").then(r => r.json());
        const h = await fetch("/api/system/health").then(r => r.json()).catch(() => ({{}}));

        const up = s.uptime_seconds ?? 0;
        const hh = Math.floor(up/3600), mm = Math.floor((up%3600)/60);
        document.getElementById("uptime").textContent = `${{hh}}h ${{mm}}m`;

        const ok = (h.status === "healthy" && h.checks && h.checks.database && h.checks.ai_engine && h.checks.news_collector);
        document.getElementById("health").textContent = ok ? "Healthy" : "Degraded";
        document.getElementById("health").className += ok ? " text-emerald-300" : " text-amber-300";
        document.getElementById("healthDetail").textContent = h ? JSON.stringify(h) : "no data";
      }} catch (e) {{
        document.getElementById("health").textContent = "Unknown";
        document.getElementById("healthDetail").textContent = "fetch failed";
      }}
    }})();
  </script>
</body>
</html>
    """)


# --- 정적 파일 마운트 (안전 버전) ---
from fastapi.staticfiles import StaticFiles
import os

if os.path.isdir("public"):
    app.mount("/", StaticFiles(directory="public", html=True), name="static")


# 개발 서버 실행
if __name__ == "__main__":
    import uvicorn
    
    logger.info("개발 서버 시작", port=8000)
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info"
    )