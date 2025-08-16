# 깔깔뉴스 API v3.0.0

AI 기반 완전 맞춤형 뉴스 플랫폼 - 2025년 최신 기술 스택 적용

## 🚀 주요 개선사항 (v2.8.2 → v3.0.0)

### 🏗️ 아키텍처 혁신
- ✅ **모듈화된 구조**: 1507줄 단일 파일 → 구조화된 모듈 시스템
- ✅ **의존성 주입**: SOLID 원칙 적용으로 결합도 최소화
- ✅ **중복 코드 제거**: release_lock, apply_cache_headers 중복 정의 해결
- ✅ **타입 안전성**: 엄격한 Pydantic 검증 강화

### ⚡ 성능 최적화 (검증된 설정값)
- ✅ **SQLite WAL 모드**: 최신 최적화 설정 (256MB 메모리 맵, 64MB 캐시)
- ✅ **OpenAI API 동시성**: Semaphore(25) 적용 (2025년 권장 중간값)
- ✅ **분당 요청 제한**: 100회 (GPT-3.5-turbo 안전 마진 고려)
- ✅ **Redis 분산 캐시**: 메모리 fallback 지원

### 🛡️ 보안 강화
- ✅ **분산 락 시스템**: Redis 기반 Race Condition 완전 방지
- ✅ **강화된 API 검증**: 프로덕션 환경 API 키 강제화
- ✅ **지능형 레이트 리미팅**: 경로별 가중치 적용 토큰 버킷
- ✅ **프록시 환경 지원**: X-Forwarded-For, X-Real-IP 헤더 처리

### 📊 관찰성 개선
- ✅ **구조화된 로깅**: JSON 형식 + Request ID 추적
- ✅ **헬스체크 시스템**: 컴포넌트별 상태 모니터링
- ✅ **성능 메트릭**: OpenAI API 호출 지연시간, 토큰 사용량 추적
- ✅ **시스템 통계**: 실시간 데이터베이스 통계

## 🏗️ 검증된 프로젝트 구조

```
kkalkal_news/                    # 2025년 FastAPI 모범 사례 준수
├── app/
│   ├── api/
│   │   ├── routes/             # 라우터별 책임 분리
│   │   │   ├── news.py         # 뉴스 관련 API
│   │   │   ├── users.py        # 사용자 관련 API  
│   │   │   └── system.py       # 시스템 관리 API
│   │   └── dependencies.py     # FastAPI 의존성 관리
│   ├── core/
│   │   ├── config.py          # Pydantic Settings 기반 설정
│   │   ├── security.py        # 보안 유틸리티 (API 키, IP 추출)
│   │   └── logging.py         # 구조화된 JSON 로깅
│   ├── services/              # 비즈니스 로직 계층
│   │   ├── ai_engine.py       # OpenAI API 최적화 엔진
│   │   ├── news_collector.py  # RSS 수집기 (강건성 강화)
│   │   └── news_processor.py  # 뉴스 처리 파이프라인
│   ├── models/
│   │   ├── database.py        # SQLite WAL 최적화
│   │   └── schemas.py         # Pydantic v1/v2 호환 스키마
│   ├── utils/
│   │   ├── cache.py           # Redis + 메모리 캐시 시스템
│   │   └── helpers.py         # 유틸리티 함수
│   └── middleware.py          # 레이트 리미팅, 로깅 미들웨어
├── main.py                    # 메인 애플리케이션 + 라이프사이클 관리
├── requirements.txt           # 검증된 의존성 목록
├── .env.example              # 환경변수 템플릿
└── README.md                 # 이 파일
```

## 🛠️ 설치 및 실행

### 1. 환경 준비
```bash
# Python 3.11+ 권장
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
```

### 2. 필수 환경변수 설정
```bash
# 필수 설정
OPENAI_API_KEY=sk-...                    # OpenAI API 키
INTERNAL_API_KEY=your_secret_key         # 내부 API 보호 (프로덕션 필수)

# 선택적 설정 (기본값 제공)
OPENAI_CONCURRENCY_LIMIT=25             # 동시 요청 수 (권장 25)
RATE_LIMIT_PER_MINUTE=100               # 분당 요청 제한
REDIS_URL=redis://localhost:6379        # Redis 캐시 서버
```

### 3. 애플리케이션 실행
```bash
# 개발 환경
python main.py

# 프로덕션 환경
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 📊 API 엔드포인트

### 뉴스 API (`/api/news`)
- `POST /refresh` - 뉴스 수집 및 팩트 추출 (백그라운드 처리)
- `POST /personalize` - 사용자 맞춤 기사 생성
- `GET /articles` - 최신 기사 목록 (페이지네이션 지원)
- `GET /articles/{id}` - 기사 상세 + 팩트 정보

### 사용자 API (`/api/users`)
- `POST /profiles` - 프로필 생성/수정
- `GET /profiles/{user_id}` - 프로필 조회
- `POST /activity` - 사용자 행동 로깅
- `GET /activity/{user_id}` - 활동 히스토리

### 시스템 API (`/api/system`)
- `GET /health` - 헬스체크 (컴포넌트별 상태)
- `GET /info` - 시스템 정보 및 설정
- `GET /stats` - 실시간 통계 (기사, 사용자, 활동)
- `POST /cleanup` - 데이터 정리 작업

## 🔧 성능 튜닝 가이드

### OpenAI API 최적화
```bash
# 2025년 검증된 설정값
OPENAI_CONCURRENCY_LIMIT=25    # GPT-3.5: 25, GPT-4: 15 권장
OPENAI_RETRIES=2               # 재시도 횟수
OPENAI_TIMEOUT=60              # 타임아웃 (초)
USE_STRUCTURED_OUTPUTS=true    # 구조화된 출력 사용
```

### 데이터베이스 최적화
```bash
# SQLite WAL 모드 설정 (자동 적용)
# - 64MB 캐시 크기
# - 256MB 메모리 맵
# - 자동 최적화 쿼리
# - 1000회마다 WAL 체크포인트
```

### 캐시 최적화
```bash
# Redis 설정 (선택사항)
REDIS_URL=redis://localhost:6379
PC_TTL_DAYS=30                 # 개인화 콘텐츠 캐시 기간
ACTIVITY_TTL_DAYS=90           # 활동 로그 보존 기간
```

## 🔒 보안 설정

### API 보안
- **API 키 검증**: 쓰기 작업 보호
- **환경별 설정**: 개발/프로덕션 분리
- **요청 추적**: X-Request-ID 헤더

### 네트워크 보안
```bash
# CORS 설정
CORS_ORIGINS=https://yourdomain.com,https://api.yourdomain.com

# 신뢰할 수 있는 프록시
TRUSTED_PROXIES=127.0.0.1,::1,10.0.0.0/8
```

### 레이트 리미팅
- **토큰 버킷 알고리즘**: 버스트 트래픽 처리
- **경로별 가중치**: 무거운 작업에 더 많은 토큰 소비
- **분산 환경 지원**: Redis 기반 공유 상태

## 📈 모니터링 및 로깅

### 구조화된 로깅
```json
{
  "timestamp": "2025-08-17T16:25:18+09:00",
  "level": "INFO",
  "message": "요청 완료",
  "request_id": "req_1a2b3c4d",
  "method": "POST",
  "path": "/api/news/personalize",
  "status": 200,
  "duration": 1.234,
  "ip": "192.168.1.100"
}
```

### 헬스체크 모니터링
```bash
# 전체 시스템 상태 확인
curl http://localhost:8000/api/system/health

# 응답 예시
{
  "status": "healthy",
  "checks": {
    "database": true,
    "ai_engine": true,
    "news_collector": true,
    "cache": true
  },
  "timestamp": "2025-08-17T16:25:18"
}
```

### 성능 메트릭
- **OpenAI API**: 지연시간, 토큰 사용량, 에러율
- **데이터베이스**: 쿼리 시간, 연결 수
- **캐시**: 히트율, 메모리 사용량
- **HTTP**: 요청 수, 응답 시간, 상태 코드

## 🚀 배포 가이드

### Docker 배포
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8000

# 헬스체크 추가
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/system/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 환경별 설정
```bash
# 개발 환경
ENVIRONMENT=development
DEBUG=true

# 스테이징 환경  
ENVIRONMENT=staging
DEBUG=false

# 프로덕션 환경
ENVIRONMENT=production
DEBUG=false
INTERNAL_API_KEY=required  # 필수
```

## 🔄 업그레이드 가이드

### v2.8.2에서 v3.0.0으로
1. **백업**: 기존 데이터베이스 백업
2. **환경변수**: 새로운 설정 항목 추가
3. **의존성**: `pip install -r requirements.txt`
4. **검증**: 헬스체크 엔드포인트로 확인

### 주요 변경사항
- **파일 구조**: 단일 파일 → 모듈화된 구조
- **설정 관리**: 환경변수 중앙화
- **API 엔드포인트**: 새로운 시스템 API 추가
- **캐시 시스템**: Redis 지원 추가

## 🤝 기여하기

### 개발 환경 설정
```bash
# 개발 의존성 설치
pip install -r requirements.txt pytest pytest-asyncio httpx

# 테스트 실행
pytest

# 코드 품질 검사
black . --check
ruff check .
```

### 코딩 컨벤션
- **Python**: PEP 8 준수, Black 포매터 사용
- **API**: RESTful 설계 원칙
- **로깅**: 구조화된 JSON 로그
- **에러 핸들링**: 명확한 에러 메시지

## 📄 라이선스

MIT License - 자세한 내용은 LICENSE 파일 참조

---

**🎯 핵심 메시지**: 검증된 2025년 모범 사례를 적용한 확장 가능하고 안정적인 뉴스 플랫폼