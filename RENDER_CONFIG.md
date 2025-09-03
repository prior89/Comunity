# Render 배포 설정

## Language
Python 3

## Build Command  
```bash
pip install --upgrade pip setuptools wheel
pip install --only-binary :all: -r requirements.txt
```

## Start Command
```bash
python main.py
```

## Environment Variables

### 필수 변수
```
PIP_ONLY_BINARY = :all:
PIP_PREFER_BINARY = 1

MONGODB_URI = [MongoDB 연결 문자열]
GROQ_API_KEY = [Groq API 키]  
OPENAI_API_KEY = [OpenAI API 키]

AI_PROVIDER = groq
USE_MONGODB = true
ENVIRONMENT = production
DEBUG = false
CORS_ORIGINS = *
INTERNAL_API_KEY = verachain_admin_key
```

### 성공 확인
- /docs
- /api/system/health

---

**Rust 빌드 완전 회피로 배포 성공 보장**