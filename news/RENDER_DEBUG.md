# Render 배포 디버깅 가이드

## 문제: requirements.txt 찾을 수 없음

### 원인 1: Root Directory 설정 오류
Render → Settings → Root Directory
- 현재: `/` (또는 비어있음)
- 변경: `/news` (requirements.txt가 있는 폴더)

### 원인 2: 파일 경로 문제  
Build Command에 파일 확인 추가:
```bash
pwd && ls -la && python -V && pip install --upgrade pip setuptools wheel && pip install --no-cache-dir --only-binary=:all: -r requirements.txt
```

### 해결 순서:
1. **Root Directory 확인**: 
   - Settings → Root Directory = `/news`
   
2. **Build Command 디버그 버전**:
   ```bash
   pwd && ls -la requirements.txt && pip install --upgrade pip setuptools wheel && pip install --no-cache-dir --only-binary=:all: -r requirements.txt
   ```

3. **재배포**:
   - Clear build cache (있다면)
   - Manual Deploy

### 빌드 로그에서 확인할 것:
```
pwd 결과가 올바른 폴더인지
ls -la에 requirements.txt가 보이는지
```

---

**Root Directory를 `/news`로 설정하는 게 핵심!**