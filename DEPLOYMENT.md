# 깔깔뉴스 API 배포 가이드

엔젤투자자가 모바일에서 사용할 수 있는 뉴스 분석 API를 클라우드에 배포하는 방법입니다.

## 🚀 빠른 배포 (Docker Compose)

### 1. 필요한 파일 준비
```bash
# .env 파일 생성 (.env.example 복사)
cp .env.example .env

# OpenAI API 키 설정
nano .env
```

### 2. 환경변수 설정 (.env 파일)
```bash
# 필수 설정
OPENAI_API_KEY=your_openai_api_key_here
INTERNAL_API_KEY=your_secret_api_key_here
USE_MONGODB=true
MONGODB_URI=mongodb://newsuser:newspass@mongodb:27017/kkalkalnews
```

### 3. 도커로 실행
```bash
# 백그라운드에서 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f news-api
```

### 4. API 테스트
```bash
# 헬스체크
curl http://localhost:8000/api/system/health

# 뉴스 수집
curl -X POST "http://localhost:8000/api/news/refresh" \
     -H "X-API-Key: your_secret_api_key_here"

# 기사 목록 조회
curl http://localhost:8000/api/news/articles
```

## ☁️ 클라우드 배포 옵션

### A) AWS ECS + MongoDB Atlas
1. **MongoDB Atlas 설정**
   ```
   https://cloud.mongodb.com/ 에서 무료 클러스터 생성
   연결 문자열 복사: mongodb+srv://username:password@cluster.mongodb.net/kkalkalnews
   ```

2. **AWS ECS 배포**
   ```bash
   # ECR에 이미지 푸시
   docker build -t kkalkalnews-api .
   docker tag kkalkalnews-api:latest your-account.dkr.ecr.region.amazonaws.com/kkalkalnews-api:latest
   docker push your-account.dkr.ecr.region.amazonaws.com/kkalkalnews-api:latest
   ```

### B) Google Cloud Run + MongoDB Atlas
```bash
# 이미지 빌드 및 푸시
gcloud builds submit --tag gcr.io/your-project/kkalkalnews-api

# Cloud Run 배포
gcloud run deploy kkalkalnews-api \
    --image gcr.io/your-project/kkalkalnews-api \
    --platform managed \
    --region asia-northeast1 \
    --allow-unauthenticated \
    --set-env-vars MONGODB_URI=your_atlas_connection_string
```

### C) Heroku (간편 배포)
```bash
# Heroku CLI로 배포
heroku create your-app-name
heroku config:set OPENAI_API_KEY=your_key
heroku config:set MONGODB_URI=your_atlas_connection_string
git push heroku main
```

## 📱 모바일 앱 연동

### React Native / Flutter에서 사용
```javascript
const API_BASE = 'https://your-deployed-api.com/api';

// 사용자 프로필 생성
const createProfile = async (profileData) => {
  const response = await fetch(`${API_BASE}/users/profiles`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profileData)
  });
  return response.json();
};

// 개인화 뉴스 요청
const getPersonalizedNews = async (articleId, userId) => {
  const response = await fetch(`${API_BASE}/news/personalize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ article_id: articleId, user_id: userId })
  });
  return response.json();
};
```

### iOS Swift에서 사용
```swift
struct NewsAPI {
    static let baseURL = "https://your-deployed-api.com/api"
    
    static func personalizeNews(articleId: String, userId: String) async throws -> PersonalizedNews {
        let url = URL(string: "\(baseURL)/news/personalize")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = ["article_id": articleId, "user_id": userId]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, _) = try await URLSession.shared.data(for: request)
        return try JSONDecoder().decode(PersonalizedNews.self, from: data)
    }
}
```

### Android Kotlin에서 사용
```kotlin
class NewsApiService {
    private val baseUrl = "https://your-deployed-api.com/api"
    
    suspend fun personalizeNews(articleId: String, userId: String): PersonalizedNews {
        val client = OkHttpClient()
        val json = JSONObject().apply {
            put("article_id", articleId)
            put("user_id", userId)
        }
        
        val request = Request.Builder()
            .url("$baseUrl/news/personalize")
            .post(json.toString().toRequestBody("application/json".toMediaType()))
            .build()
            
        return client.newCall(request).execute().use { response ->
            // JSON 파싱 로직
        }
    }
}
```

## 🛡️ 보안 설정

### 프로덕션 환경 권장 사항
```bash
# CORS 특정 도메인만 허용
CORS_ORIGINS=https://yourdomain.com,capacitor://localhost

# API 키 강화
INTERNAL_API_KEY=복잡한-64자-이상-키

# HTTPS 필수 (Nginx 설정)
# SSL 인증서 Let's Encrypt 사용 권장
```

## 📊 모니터링

### API 상태 확인 엔드포인트
- `GET /api/system/health` - 기본 헬스체크
- `GET /api/system/metrics` - 성능 메트릭
- `GET /api/system/stats` - 사용 통계

### 로그 확인
```bash
# Docker 로그
docker-compose logs -f news-api

# MongoDB 로그
docker-compose logs -f mongodb
```

## 🔧 문제 해결

### 일반적인 문제들
1. **MongoDB 연결 실패**
   - 연결 문자열 확인
   - 네트워크 접근 권한 확인
   - MongoDB 서버 상태 확인

2. **API 키 인증 실패**
   - .env 파일의 INTERNAL_API_KEY 확인
   - 헤더에 `X-API-Key` 설정 확인

3. **CORS 오류 (모바일)**
   - CORS_ORIGINS에 적절한 도메인 추가
   - 모바일: `capacitor://localhost`, `ionic://localhost` 추가

### 지원 정보
- API 문서: `http://your-domain/docs`
- 헬스체크: `http://your-domain/api/system/health`
- 깃허브 이슈: 문제 발생시 이슈 등록

이제 엔젤투자자들이 어디서든 모바일로 뉴스를 분석하고 투자 인사이트를 얻을 수 있습니다! 🚀📱