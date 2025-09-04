# Render Environment Group 설정 가이드

## Environment Group 생성

### 1. Render 대시보드에서 Environment Group 생성
- 대시보드 → Environment Groups → "Create Environment Group"
- **그룹 이름**: `ai-news-secrets`

### 2. 필수 환경변수 추가

#### 🔴 AI API Keys (필수)
```bash
OPENAI_API_KEY=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
GROQ_API_KEY=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
```

#### 🔴 Database 연결 (필수)
```bash
MONGODB_URI=mongodb+srv://verachain:1674614ppappa@verachain-clusters.izpeptn.mongodb.net/?retryWrites=true&w=majority&appName=verachain-clusters
USE_MONGODB=true
```

#### 🔴 AI 설정 (필수)
```bash
AI_PROVIDER=dual
OPENAI_MODEL=gpt-4o-mini
GROQ_MODEL=llama-3.3-70b-versatile
```

#### 🟡 기타 설정 (권장)
```bash
OPENAI_TIMEOUT=60
OPENAI_RETRIES=2
PYTHON_VERSION=3.12
DEBUG=false
```

## render.yaml 연결

```yaml
services:
  - type: web
    name: ai-news-platform
    env: python
    plan: starter
    buildCommand: cd news && python -m pip install --upgrade pip setuptools wheel && python -m pip install -r requirements-render.txt
    startCommand: cd news && uvicorn main:app --host 0.0.0.0 --port $PORT
    autoDeploy: true
    envVarGroups:
      - ai-news-secrets  # 👈 Environment Group 연결
```

## 배포 순서

1. **Environment Group 생성**: `ai-news-secrets`
2. **환경변수 추가**: 위 필수/권장 변수들 입력
3. **render.yaml 커밋**: `envVarGroups` 섹션 포함
4. **Git Push**: 자동 배포 트리거
5. **배포 확인**: 환경변수가 자동 주입되어 서비스 정상 작동

## 장점

✅ **영구 보존**: 환경변수가 그룹에 영구 저장  
✅ **보안**: API 키가 코드에 노출되지 않음  
✅ **재사용**: 다른 서비스에서도 같은 그룹 사용 가능  
✅ **자동 주입**: 배포할 때마다 자동으로 환경변수 적용  

---
*생성일: 2025-09-04 05:25*