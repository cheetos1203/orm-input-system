# OMR 입력 + 성적처리 시스템 (오픈소스 우선, API 폴백)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/cheetos1203/orm-input-system)

이 프로젝트는 다음 목표를 위한 MVP입니다.

- 기본 인식: **완전 로컬 오픈소스(OpenCV + Tesseract)** 로 처리 (API 비용 0원)
- 오류 처리: 신뢰도 낮은 항목만 **선별 추출**
- 고도화 인식: 선별 항목만 **AI API 폴백** (선택 사용)
- 운영 편의: 오류 이유를 보여주고, 관리자 화면에서 수정 후 확정

## 1) 핵심 아키텍처

1. PDF/이미지 업로드
2. 전처리(왜곡 보정, 이진화, 버블 영역 추출)
3. OMR 기본 판독(OpenCV 기반)
4. 문자인식(이름/학번 등: Tesseract)
5. 신뢰도 평가
6. 불확실 항목만 `needs_review`로 분리
7. (옵션) API 폴백 재인식
8. 오류 원인 설명 생성
9. 관리자 수동수정 후 성적 확정
10. CSV/엑셀 내보내기

## 2) 빠른 시작

### 요구사항

- Python 3.11+
- Windows 기준 Tesseract 설치 권장

### 설치

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 실행

```bash
uvicorn app.main:app --reload
```

또는:

```bash
python run_web.py
```

브라우저:

- 홈: `http://127.0.0.1:8000/`
- API 문서: `http://127.0.0.1:8000/docs`
- 검수 UI: `http://127.0.0.1:8000/review`
- 최신 결과: `http://127.0.0.1:8000/result`
- 결과 페이지: `http://127.0.0.1:8000/result/{sheet_id}`

## 2-1) 웹 서비스 빠른 실행 (Windows)

- 배치 파일 실행: `start_web.bat`
- PowerShell 실행: `./start_web.ps1`

위 스크립트는 가상환경 생성, 패키지 설치, 서버 실행까지 자동으로 수행합니다.

## 2-2) Docker 실행

### 1) Docker Compose

```bash
docker compose up --build
```

### 2) Docker 단독 실행

```bash
docker build -t omr-web .
docker run -p 8000:8000 --name omr-web omr-web
```

접속:

- `http://127.0.0.1:8000/`

## 3) 폴더 구조

```text
app/
  main.py
  config.py
  models.py
  storage.py
  explain.py
  pipeline/
    preprocess.py
    omr.py
    ocr.py
    confidence.py
    fallback_api.py
  templates/
    index.html
    result.html
    review.html
data/
  uploads/
  outputs/
  review/
run_web.py
start_web.bat
start_web.ps1
Dockerfile
docker-compose.yml
```

## 4) API 비용 제어 전략

- `ENABLE_FALLBACK_API=false` 기본값
- `CONFIDENCE_THRESHOLD` 미만 항목만 API 전송
- 전체 페이지가 아니라 **문제별 ROI 조각 이미지**만 전송
- API 실패 시 로컬 결과 + 수동검수로 안전 복귀

## 5) 환경 변수

`.env.example`를 복사하여 `.env` 생성:

```env
ENABLE_FALLBACK_API=false
CONFIDENCE_THRESHOLD=0.75
TESSERACT_CMD=
FALLBACK_PROVIDER=openai
FALLBACK_API_URL=
FALLBACK_API_KEY=
APP_HOST=127.0.0.1
APP_PORT=8000
APP_RELOAD=true
APP_WORKERS=1
```

## 6) 다음 단계(현장 적용)

- 실제 시험지 템플릿 좌표(JSON) 등록
- 정답표 업로드/버전관리
- 학교별 양식에 맞춘 결과 엑셀 템플릿 출력
- 검수 이력/수정 이력 감사 로그

## 7) 실제 사용 순서

1. `data/layout.example.json`을 `data/layout.json`으로 복사하고 좌표 보정
2. `data/report_config.example.json`을 `data/report_config.json`으로 복사하고 학교/회차/영역 설정 입력
3. 정답표 등록 (`/api/answer-key`)
4. 시험지 이미지/PDF 업로드 (`/api/ingest`)
5. 검수 화면(`/review`)에서 오류 항목만 수정
6. CSV 내보내기 (`/api/export/csv`)

`/api/results`에서 `sheet_id`를 확인한 뒤 `/result/{sheet_id}`를 열면 성적표 페이지가 출력됩니다.
`/api/ingest` 응답에는 `result_urls`가 포함되어 업로드 직후 결과 페이지로 이동할 수 있습니다.

정답표 등록 예시:

```json
{
  "version": "2026-모의-4주차-C",
  "answer_key": {
    "1": "B",
    "2": "D",
    "3": "A"
  }
}
```
