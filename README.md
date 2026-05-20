# (주)리치시스템 — 분양 시세조사 API 백엔드

국토부 실거래 + 카카오 로컬 API를 통합한 Flask 백엔드. GitHub Pages 프론트엔드에서 CORS로 호출 가능.

---

## 🚀 Render.com 배포 (무료, 5분 소요)

### 1. GitHub 저장소 생성

본인 계정에 새 저장소 생성: `richsystem-backend` (Public)

이 폴더의 4개 파일 업로드:
- `app.py`
- `requirements.txt`
- `Procfile`
- `render.yaml`

### 2. Render 가입 & 연결

1. https://render.com 접속 → **Get Started for Free** (GitHub 계정으로 가입)
2. Dashboard → **New +** → **Web Service**
3. GitHub 저장소 연결 → `richsystem-backend` 선택
4. 자동으로 `render.yaml` 인식 → **Apply**

### 3. 환경변수 설정 (필수)

배포 후 서비스 페이지 → **Environment** 탭:

| Key | Value |
|---|---|
| `MOLIT_API_KEY` | 공공데이터포털 발급 받은 서비스키 (Decoding 키) |
| `KAKAO_REST_KEY` | 카카오 REST API 키 (`KakaoAK ` 접두어 X) |

**API 키 받는 곳:**
- 국토부: https://www.data.go.kr → "오피스텔 매매 실거래자료" 신청 (즉시 발급)
- 카카오: https://developers.kakao.com → 앱 → 일반 → REST API 키

### 4. 배포 확인

3~5분 후 URL 발급: `https://richsystem-backend.onrender.com`

테스트:
```
https://richsystem-backend.onrender.com/api/health
```

응답:
```json
{
  "status": "ok",
  "molit_key": true,
  "kakao_key": true,
  "supported_sigungu": 60
}
```

---

## 📡 API 사용법

### `GET /api/analyze`

분양 시세 종합 분석 (매매·전월세 통합)

**Query Params:**
- `address` (필수): 주소 또는 지번
- `proj` (선택): 현장명
- `months` (선택): 조회 기간 (기본 6개월)

**예시:**
```
GET /api/analyze?address=서울특별시 영등포구 여의도동 17-4&proj=파크라움 여의도&months=6
```

**응답 (요약):**
```json
{
  "address": "서울특별시 영등포구 여의도동 17-4",
  "sigungu_code": "11560",
  "sigungu_name": "영등포구",
  "coords": {"lat": 37.5219, "lng": 126.9245},
  "pricing": {
    "comparables": [
      {
        "name": "여의도 자이엘라",
        "year": "2020",
        "area_m2": 40.8,
        "amount_manwon": 54200,
        "pyung_price": 2792,
        "sample_count": 3
      },
      ...
    ],
    "stats": {
      "count": 8,
      "total_transactions": 47,
      "min_pyung": 2253,
      "max_pyung": 3357,
      "avg_pyung": 2707,
      "median_pyung": 2728
    }
  },
  "rent": {
    "jeonse_median": 32000,
    "wolse_median": 85,
    ...
  }
}
```

### `GET /api/health`

서비스 상태 확인 (API 키 등록 여부 등)

---

## ⚠️ 무료 티어 제약

- **Sleep**: 15분 idle 후 슬립 → 첫 호출시 30~50초 콜드 스타트
- **Bandwidth**: 월 100GB
- **Compute**: 무제한 (저트래픽 OK)

콜드 스타트 줄이려면 cron 서비스 (예: `cron-job.org`)로 5분마다 `/api/health` 호출 권장.

---

## 🔧 로컬 개발

```bash
cd backend
pip install -r requirements.txt

# 환경변수 설정 (Windows PowerShell)
$env:MOLIT_API_KEY="your_key_here"
$env:KAKAO_REST_KEY="your_kakao_key"

python app.py
```

브라우저: `http://localhost:5000/api/health`

---

## 📝 지원 지역

현재 60개 시군구 매핑 (서울 25 + 부산·울산·대구·광주·대전·인천·세종·경기 주요). 추가 필요시 `app.py`의 `SIGUNGU_CODES` 딕셔너리에 추가.

행정코드 5자리 출처: https://www.code.go.kr/stdcode/regCodeL.do
