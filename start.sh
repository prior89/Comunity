#!/bin/bash
# Render.com 배포용 시작 스크립트

echo "🚀 VeraChain News API 시작 중..."
echo "Environment: $ENVIRONMENT"
echo "MongoDB: $USE_MONGODB"
echo "Port: $PORT"

# Python 경로 설정
export PYTHONPATH=/opt/render/project/src:$PYTHONPATH

# Uvicorn으로 FastAPI 실행
exec python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1