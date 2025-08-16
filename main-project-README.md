# 깔깔뉴스 API v3.0.0

AI 기반 완전 맞춤형 뉴스 플랫폼 - 모듈화된 아키텍처 및 2025년 최적화 적용

## 🚀 주요 개선사항

### 아키텍처 개선
- ✅ 모듈화된 프로젝트 구조 (1500줄+ 단일 파일 → 구조화된 모듈)
- ✅ 의존성 주입 패턴 적용
- ✅ 중복 함수 정의 문제 해결
- ✅ 타입 안정성 강화

### 성능 최적화
- ✅ SQLite WAL2 모드 최적화 (256MB 메모리 맵, 64MB 캐시)
- ✅ OpenAI API 동시성 최적화 (3 → 10 세마포어)
- ✅ Redis 기반 분산 캐시 시스템
- ✅ 지능형 레이트 리미팅 (토큰 버킷 + 경로별 가중치)

### 보안 강화
- ✅ Redis 기반 분산 락으로 Race Condition 방지
- ✅ 강화된 API 키 검증
- ✅ 프록시 환경 지원 강화
- ✅ CORS 설정 최적화

### 관찰성 개선
- ✅ 구조화된 JSON 로깅
- ✅ Request ID 기반 추적
- ✅ 헬스체크 엔드포인트
- ✅ 시스템 메트릭 및 통계

## 🏗️ 프로젝트 구조

```
project/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── news.py      # 뉴스 관련 API
│   │   │   ├── users.py     # 사용자 관련 API
│   │   │   └── system.py    # 시스템 관련 API
│   │   └── dependencies.py  # FastAPI 의존성
│   ├── core/
│   │   ├── config.py        # 설정 관리
│   │   ├── security.py      # 보안 유틸리티
│   │   └── logging.py       # 구조화된 로깅
│   ├── services/
│   │   ├── ai_engine.py     # AI 엔진 (OpenAI)
│   │   ├── news_collector.py # 뉴스 수집기
│   │   └── news_processor.py # 뉴스 처리 파이프라인
│   ├── models/
│   │   ├── database.py      # 데이터베이스 관리
│   │   └── schemas.py       # Pydantic 스키마
│   ├── utils/
│   │   ├── cache.py         # Redis 캐시 시스템
│   │   └── helpers.py       # 유틸리티 함수
│   └── middleware.py        # 미들웨어 모음
├── main.py                  # 메인 애플리케이션
├── requirements.txt         # Python 의존성
├── .env.example            # 환경변수 예시
└── README.md               # 이 파일
```

## 🛠️ 설치 및 실행

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정
```bash
cp .env.example .env
# .env 파일을 편집하여 실제 값 입력
```

### 3. 필수 환경변수
```bash
OPENAI_API_KEY=your_openai_api_key_here
INTERNAL_API_KEY=your_internal_api_key_here  # 프로덕션 필수
```

### 4. 애플리케이션 실행
```bash
# 개발 서버
python main.py

# 또는 uvicorn 직접 실행
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 📊 API 엔드포인트

### 뉴스 관련
- `POST /api/news/refresh` - 뉴스 수집 및 처리
- `POST /api/news/personalize` - 기사 개인화
- `GET /api/news/articles` - 기사 목록 조회
- `GET /api/news/articles/{article_id}` - 기사 상세 조회

### 사용자 관련
- `POST /api/users/profiles` - 사용자 프로필 생성/수정
- `GET /api/users/profiles/{user_id}` - 사용자 프로필 조회
- `POST /api/users/activity` - 사용자 활동 로깅
- `GET /api/users/activity/{user_id}` - 사용자 활동 히스토리

### 시스템 관련
- `GET /api/system/health` - 시스템 상태 확인
- `GET /api/system/info` - 시스템 정보
- `GET /api/system/stats` - 시스템 통계
- `POST /api/system/cleanup` - 데이터 정리

## 🔧 설정 옵션

### 성능 튜닝
```bash
# OpenAI API 최적화
OPENAI_CONCURRENCY_LIMIT=10  # 동시 요청 수
OPENAI_RETRIES=2             # 재시도 횟수
RATE_LIMIT_PER_MINUTE=100    # 분당 요청 제한

# 배치 처리
ARTICLES_PER_BATCH=5         # 배치당 기사 수
COLLECT_TIMEOUT=30           # 수집 타임아웃(초)
```

### 데이터 보존
```bash
PC_TTL_DAYS=30              # 개인화 콘텐츠 보존 기간
ACTIVITY_TTL_DAYS=90        # 활동 로그 보존 기간
```

### 고급 기능
```bash
USE_STRUCTURED_OUTPUTS=true # OpenAI Structured Outputs 사용
REDIS_URL=redis://localhost:6379  # Redis 캐시 서버
```

## 🔒 보안 설정

### API 키 보호
- 프로덕션 환경에서는 `INTERNAL_API_KEY` 필수
- 쓰기 작업에 대한 API 키 검증
- 환경별 설정 분리

### 네트워크 보안
- CORS 정책 설정
- 신뢰할 수 있는 프록시 설정
- 레이트 리미팅

## 📈 모니터링

### 구조화된 로깅
- JSON 형식 로그 출력
- Request ID 기반 추적
- 성능 메트릭 포함

### 헬스체크
```bash
curl http://localhost:8000/api/system/health
```

### 시스템 통계
```bash
curl http://localhost:8000/api/system/stats
```

## 🚀 배포

### Docker 예시
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 환경별 설정
- `ENVIRONMENT=development|staging|production`
- `DEBUG=true|false`
- 프로덕션에서는 API 문서 비활성화

## 🔄 마이그레이션 가이드

기존 v2.8.2에서 v3.0.0으로 업그레이드:

1. 환경변수 설정 업데이트
2. 모듈화된 구조로 코드 분리
3. Redis 설치 및 설정 (선택사항)
4. 새로운 API 엔드포인트 적용

## 🤝 기여하기

1. 이슈 리포팅: 문제점 또는 개선사항 제안
2. 코드 기여: 풀 리퀘스트 생성
3. 문서 개선: README 및 코드 문서 개선

## 📄 라이선스

MIT License - 자세한 내용은 LICENSE 파일 참조