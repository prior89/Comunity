# AI 뉴스 개인화 플랫폼 API 사양서

## 🚀 개요
실시간 뉴스 → 5W1H 구조화 → 개인맞춤 기사 생성 API  
**특허 기술** 기반 다차원 사용자 프로필 분석

## 🔑 인증
```
Authorization: Bearer <API_TOKEN>
X-Internal-Api-Key: <API_TOKEN>
Content-Type: application/json
```

## 📡 주요 엔드포인트

### **1. 뉴스 개인화 (핵심 API)**
```http
POST /api/news/personalize
```

**요청 예시:**
```json
{
  "article_id": "7e080ac387ce52a4dbfad9e3",
  "user_id": "demo_investor"
}
```

**응답 예시:**
```json
{
  "ok": true,
  "provider": "groq",
  "personalized_article": "북중 정상회담으로 동북아 증시 상승 모멘텀이 확인됐다고 전했다. 투자자들이 주목해야 할 포인트는...",
  "title": "6년 만에 동지 만나 김정은·시진핑 '끈끈함' 과시",
  "key_points": [
    "투자자 관점 분석",
    "AI 기반 맞춤형 재구성", 
    "실시간 뉴스 처리"
  ],
  "reading_time": "2분",
  "is_fallback": false
}
```

### **2. 최신 기사 조회**
```http
GET /api/news/articles?limit=10&source=연합뉴스
```

**응답 예시:**
```json
{
  "articles": [
    {
      "id": "7e080ac387ce52a4dbfad9e3",
      "title": "6년 만에 동지 만나 김정은·시진핑 '끈끈함' 과시",
      "source": "연합뉴스",
      "license": "RSS_PUBLIC",
      "copyright": "© 연합뉴스. All rights reserved.",
      "published": "2025-09-05T01:47:42+09:00",
      "collected_at": "2025-09-05T02:51:44.209722+09:00"
    }
  ],
  "count": 1
}
```

### **3. 사용자 프로필 생성**
```http
POST /api/users/profiles
```

**요청 예시:**
```json
{
  "user_id": "demo_investor",
  "age": 40,
  "job_categories": ["Investment"],
  "interests_finance": ["주식", "부동산"],
  "reading_mode": "concise"
}
```

**응답 예시:**
```json
{
  "ok": true,
  "profile": {
    "user_id": "demo_investor",
    "role": "투자자",
    "interests": ["주식", "부동산"],
    "reading_mode": "concise"
  },
  "provider": "step1_stable"
}
```

### **4. 시스템 상태 확인**
```http
GET /api/system/health
```

**응답 예시:**
```json
{
  "status": "healthy",
  "checks": {
    "database": true,
    "ai_engine": true, 
    "news_collector": true,
    "cache": true
  },
  "timestamp": "2025-09-05T08:15:30.013716"
}
```

### **5. 성능 지표 대시보드**
```http
GET /api/dashboard/metrics?hours=24
```

**응답 예시:**
```json
{
  "api_performance": {
    "total_requests": 150,
    "success_rate": 98.0,
    "response_times": {
      "p50": 2650,
      "p95": 4200, 
      "avg": 2890
    }
  },
  "ai_provider_stats": {
    "groq": {
      "requests": 25,
      "successes": 22,
      "avg_response_time": 2100,
      "primary_model": "gemma2-9b-it"
    }
  }
}
```

## 🔒 보안/컴플라이언스

### **Rate Limiting**
- **기본**: 100 RPS
- **버스트**: 200 RPS (1분)

### **데이터 보호**
- **PII 수집 금지**: 개인정보 미저장
- **로그 보관**: 30일 (감사 목적)
- **암호화**: TLS 1.3

### **IP 허용 목록**
```
# PoC 파트너 도메인
*.fnguide.com
*.deepsearch.com
*.dable.io
```

## ⚡ 성능 지표

### **응답 시간**
- **p50**: ≤ 9초
- **p95**: ≤ 15초
- **평균**: ~3초

### **안정성**
- **가용성**: 99.9%
- **성공률**: ≥ 98%
- **폴백 시간**: < 1초

## 🔧 에러 코드

| **코드** | **의미** | **대응** |
|---------|---------|---------|
| 200 | 정상 처리 | - |
| 400 | 요청 오류 | 요청 형식 확인 |
| 401 | 인증 실패 | API 토큰 확인 |
| 429 | 속도 제한 | 재시도 (백오프) |
| 500 | 서버 오류 | 자동 폴백 실행 |

## 📞 기술 지원
- **응답 시간**: 24시간 이내
- **긴급 연락**: [연락처]
- **운영 시간**: 24/7 모니터링

---
*버전: v3.0.8 | 업데이트: 2025-09-05*