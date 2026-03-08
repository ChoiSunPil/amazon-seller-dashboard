# Amazon Seller Dashboard — CLAUDE.md

## 프로젝트 개요

Amazon Sponsored Products 광고의 **ROAS 자동 최적화 대시보드**.
Amazon Advertising API를 통해 데이터를 주기적으로 수집하고,
분석 엔진이 입찰가·네거티브 키워드·예산을 자동 조정한다.

- **목표 ROAS**: 5.0 (목표 ACoS: 20%)
- **제품 카테고리**: 강아지 기저귀 라이너 (dog diaper liners)
- **광고 유형**: Sponsored Products (SP)

---

## 기술 스택

| 레이어 | 기술 |
|--------|------|
| Backend API | FastAPI (Python 3.13+) |
| 패키지 관리 | uv (pyproject.toml) |
| Amazon API | Amazon Advertising API v3 (REST, OAuth 2.0) |
| 스케줄러 | APScheduler 또는 cron |
| 데이터 저장 | SQLite (개발) → PostgreSQL (프로덕션 고려) |
| 대시보드 UI | (추후 결정 — FastAPI + Jinja2 또는 별도 프론트) |

---

## 디렉터리 구조 (목표)

```
amazon-seller-dashboard/
├── CLAUDE.md               ← 이 파일
├── main.py                 ← FastAPI 앱 진입점
├── pyproject.toml
├── uv.lock
│
├── app/
│   ├── __init__.py
│   ├── config.py           ← 환경변수, 설정값 (TARGET_ROAS 등)
│   ├── auth/
│   │   └── amazon_oauth.py ← Amazon OAuth 2.0 토큰 관리
│   ├── api/
│   │   ├── reports.py      ← Amazon 리포트 요청/다운로드
│   │   ├── campaigns.py    ← 캠페인 조회/수정
│   │   ├── keywords.py     ← 키워드 입찰가 조정
│   │   └── negatives.py    ← 네거티브 키워드 관리
│   ├── engine/
│   │   ├── optimizer.py    ← ROAS 최적화 핵심 로직
│   │   ├── bid_calculator.py ← 적정 입찰가 계산
│   │   └── harvester.py    ← Exact 수확 로직
│   ├── scheduler/
│   │   └── jobs.py         ← 주기적 분석·적용 스케줄러
│   ├── models/
│   │   └── schemas.py      ← Pydantic 모델
│   └── routers/
│       ├── dashboard.py    ← 대시보드 API 엔드포인트
│       └── health.py       ← 헬스체크
│
├── data/                   ← CSV 파일 기반 테스트용 샘플 데이터
│   └── sample/
├── tests/
└── .env.example            ← 환경변수 템플릿 (실제 .env는 gitignore)
```

---

## 핵심 비즈니스 로직

### ROAS / ACoS 관계
```
ROAS = 매출 / 광고비
ACoS = 광고비 / 매출 = 1 / ROAS

목표 ROAS 5.0  →  목표 ACoS 20%
```

### 적정 입찰가(CPC) 계산 공식
```
target_CPC = ASP × CVR × target_ACoS
           = (매출 / 주문수) × (주문수 / 클릭수) × 0.20
           = 매출 / 클릭수 × 0.20
```

### 키워드 액션 분류 기준
| 조건 | 액션 |
|------|------|
| 주문=0, 광고비 ≥ $5 | `negative_candidate` → 네거티브 등록 |
| ACoS > 25% (목표×1.25) | `bid_decrease` → 입찰 인하 |
| ROAS > 6.0 (목표×1.20) | `bid_increase` → 입찰 인상 |
| 그 외 | `maintain` → 유지 |
| Auto/Broad, 주문 ≥ 2, 클릭 ≥ 10 | `harvest_to_exact` → Exact 수확 |

### 안전 제한값
- 1회 입찰 변경 최대: ±30%
- 입찰 변경 최소 데이터 기준: 클릭 5회 이상
- 최소 입찰가: $0.05

---

## Amazon Advertising API 주요 엔드포인트

```
BASE: https://advertising-api.amazon.com

# 리포트 (비동기 — 요청 후 폴링)
POST   /reporting/reports                ← 리포트 생성 요청
GET    /reporting/reports/{reportId}     ← 상태 확인 & 다운로드 URL
GET    {downloadUrl}                     ← 실제 CSV 다운로드

# 캠페인 관리
GET    /sp/campaigns                     ← 캠페인 목록
PUT    /sp/campaigns                     ← 예산/상태 수정

# 키워드
GET    /sp/keywords                      ← 키워드 목록
PUT    /sp/keywords                      ← 입찰가 수정
POST   /sp/negativeKeywords             ← 네거티브 추가

# 검색어 타겟팅
GET    /sp/targets                       ← 타겟 목록
PUT    /sp/targets                       ← 타겟 입찰가 수정
```

### API 인증 흐름 (OAuth 2.0)
```
1. LWA(Login With Amazon)로 Authorization Code 발급
2. access_token + refresh_token 획득
3. access_token 만료(1시간)마다 refresh_token으로 갱신
4. 모든 요청 헤더: Authorization: Bearer {access_token}
                   Amazon-Advertising-API-ClientId: {client_id}
                   Amazon-Advertising-API-Scope: {profile_id}
```

### 필요한 환경변수 (.env)
```
AMAZON_CLIENT_ID=
AMAZON_CLIENT_SECRET=
AMAZON_REFRESH_TOKEN=
AMAZON_PROFILE_ID=          # 광고 프로필 ID
AMAZON_MARKETPLACE_ID=      # e.g. ATVPDKIKX0DER (US)
TARGET_ROAS=5.0
API_PORT=8000
```

---

## 개발 명령어

```bash
# 의존성 설치
uv sync

# 개발 서버 실행
uv run uvicorn main:app --reload --port 8000

# 테스트
uv run pytest

# 환경변수 설정
cp .env.example .env
# .env 파일에 실제 값 입력
```

---

## 데이터 흐름 (자동화 파이프라인)

```
[Amazon Advertising API]
        │
        │ ① 매 4시간 — 리포트 요청 (Search Term + Targeting)
        ▼
[app/api/reports.py]  — 비동기 폴링, CSV 파싱
        │
        │ ② 파싱된 데이터
        ▼
[app/engine/optimizer.py]  — ROAS 분석, 액션 결정
        │
        ├── bid_decrease/increase → [app/api/keywords.py] → PUT /sp/keywords
        ├── negative_candidate   → [app/api/negatives.py] → POST /sp/negativeKeywords
        └── harvest_to_exact     → [app/api/keywords.py] → POST /sp/keywords (Exact)
        │
        │ ③ 결과 저장
        ▼
[SQLite / 로그]  — 액션 이력 기록
        │
        ▼
[app/routers/dashboard.py]  — 대시보드 API로 노출
```

---

## 개발 단계 (Roadmap)

### Phase 1 — 기반 구축 ✅ 완료
- [x] FastAPI 프로젝트 초기화 (`main.py`)
- [x] 환경변수 및 설정 구조 (`app/config.py`)
- [x] Amazon OAuth 인증 모듈 (`app/auth/amazon_oauth.py`)
- [x] 헬스체크 라우터 (`app/routers/health.py`)

### Phase 2 — 데이터 수집 ✅ 완료
- [x] 리포트 요청 / 폴링 / 다운로드 (`app/api/reports.py`)
- [x] Pydantic 데이터 모델 (`app/models/schemas.py`)
- [x] 공통 HTTP 클라이언트 — retry / backoff (`app/api/base.py`)
- [x] 파싱 로직 단위 테스트 (`tests/test_reports.py` — 7/7 통과)

### Phase 3 — 최적화 엔진 ✅ 완료 (분석) / ⏳ 대기 (실행)
- [x] ROAS 분석 및 액션 분류 (`app/engine/optimizer.py`)
- [x] 적정 입찰가 계산 (`app/engine/bid_calculator.py`)
- [x] Exact 수확 로직 (`app/engine/harvester.py`)
- [x] 비즈니스 로직 단위 테스트 (`tests/test_optimizer.py` — 19/19 통과)
- [ ] **⏳ API 키 수령 후 작업** — 입찰가 자동 조정 (`app/api/keywords.py`) → `PUT /sp/keywords`
- [ ] **⏳ API 키 수령 후 작업** — 네거티브 키워드 자동 등록 (`app/api/negatives.py`) → `POST /sp/negativeKeywords`
- [ ] **⏳ API 키 수령 후 작업** — 스케줄러 (`app/scheduler/jobs.py`) → 4시간 주기 자동 실행

### Phase 4 — 대시보드 🚧 진행 중
- [ ] 성과 조회 API 엔드포인트 (`app/routers/dashboard.py`)
- [ ] 액션 이력 조회
- [ ] 실시간 ROAS 트래킹 UI

---

## 코드 컨벤션

- Python: PEP 8, type hints 필수
- 비동기: `async/await` 적극 사용 (API 호출은 모두 async)
- 에러 핸들링: Amazon API rate limit (429) 대응 필수 — exponential backoff
- 환경변수: 하드코딩 금지, 반드시 `.env`에서 로드
- 로깅: `logging` 모듈 사용, API 호출/응답 모두 기록

---

## 참고 자료

- [Amazon Advertising API 공식 문서](https://advertising.amazon.com/API/docs/)
- [LWA(Login with Amazon) 인증](https://developer.amazon.com/docs/login-with-amazon/)
- 기존 분석 로직: `data/sample/` 폴더의 CSV 파일 및 초기 분석 스크립트 참고
