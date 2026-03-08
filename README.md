# Amazon SP ROAS 최적화 대시보드

Amazon Sponsored Products 광고의 ROAS를 자동으로 분석하고 최적화 액션을 제안하는 FastAPI 기반 대시보드.

- **목표 ROAS**: 5.0 (목표 ACoS: 20%)
- **제품 카테고리**: 강아지 기저귀 라이너 (dog diaper liners)

---

## 빠른 시작

```bash
# 1. 의존성 설치
uv sync

# 2. 환경변수 설정 (API 키 없이도 샘플 데이터로 동작)
cp .env.example .env

# 3. 서버 실행
uv run uvicorn main:app --reload --port 8000
```

서버 실행 후 `dashboard_ui.html` 파일을 브라우저로 열면 시각적 대시보드를 확인할 수 있습니다.

---

## 주요 기능

- **ROAS 분석**: 키워드별 ROAS / ACoS 자동 계산
- **입찰가 최적화**: 목표 ACoS 기반 적정 CPC 계산 및 인상/인하 권장
- **네거티브 키워드**: 전환 없이 소진된 검색어 자동 식별
- **Exact 수확**: Auto/Broad에서 성과 좋은 검색어를 Exact로 전환 제안
- **샘플 데이터 fallback**: API 키 없이도 즉시 동작 (개발/데모 환경)

---

## 프로젝트 구조

```
amazon-seller-dashboard/
├── main.py                      # FastAPI 앱 진입점
├── dashboard_ui.html            # 시각적 대시보드 UI
├── pyproject.toml
├── .env.example                 # 환경변수 템플릿
│
├── app/
│   ├── config.py                # 환경변수 설정 (TARGET_ROAS 등)
│   ├── auth/
│   │   └── amazon_oauth.py      # Amazon OAuth 2.0 토큰 관리
│   ├── api/
│   │   ├── base.py              # 공통 HTTP 클라이언트 (retry / backoff)
│   │   └── reports.py           # 리포트 요청 / 폴링 / 다운로드
│   ├── engine/
│   │   ├── optimizer.py         # ROAS 분석 및 액션 분류
│   │   ├── bid_calculator.py    # 적정 입찰가 계산
│   │   └── harvester.py         # Exact 수확 로직
│   ├── models/
│   │   └── schemas.py           # Pydantic 데이터 모델
│   └── routers/
│       ├── health.py            # 헬스체크
│       └── dashboard.py         # 대시보드 API 엔드포인트
│
├── data/sample/                 # 테스트용 샘플 CSV
└── tests/
    ├── test_reports.py          # 파싱 로직 테스트 (7개)
    ├── test_optimizer.py        # 비즈니스 로직 테스트 (19개)
    └── test_dashboard.py        # 엔드포인트 테스트 (26개)
```

---

## API 엔드포인트

서버 실행 후 http://localhost:8000/docs 에서 Swagger UI로 직접 테스트 가능.

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/` | 서비스 상태 확인 |
| GET | `/health` | 헬스체크 |
| GET | `/dashboard/status` | 전체 ROAS 현황 요약 |
| GET | `/dashboard/campaigns` | 캠페인별 성과 집계 |
| GET | `/dashboard/actions` | 최적화 액션 목록 (필터 지원) |
| GET | `/dashboard/harvest` | Exact 수확 후보 목록 |

### 액션 필터 예시

```bash
# 네거티브 후보만 조회
GET /dashboard/actions?action_type=negative_candidate

# 광고비 $10 이상만 조회
GET /dashboard/actions?min_spend=10
```

---

## 핵심 비즈니스 로직

```
ROAS     = 매출 / 광고비
ACoS     = 광고비 / 매출  →  목표 20%
target_CPC = (매출 / 클릭수) × 0.20
```

### 키워드 액션 분류 기준

| 조건 | 액션 |
|------|------|
| 주문=0, 광고비 ≥ $5 | 네거티브 등록 |
| ACoS > 25% | 입찰 인하 |
| ROAS > 6.0 | 입찰 인상 |
| Auto/Broad, 주문 ≥ 2, 클릭 ≥ 10 | Exact 수확 |
| 그 외 | 유지 |

### 안전 제한값

- 1회 입찰 변경 최대: ±30%
- 최소 데이터 기준: 클릭 5회 이상
- 최소 입찰가: $0.05

---

## 환경변수

```bash
AMAZON_CLIENT_ID=        # Amazon Advertising API 클라이언트 ID
AMAZON_CLIENT_SECRET=    # 클라이언트 시크릿
AMAZON_REFRESH_TOKEN=    # OAuth refresh token
AMAZON_PROFILE_ID=       # 광고 프로필 ID
AMAZON_MARKETPLACE_ID=   # 마켓플레이스 ID (US: ATVPDKIKX0DER)
TARGET_ROAS=5.0          # 목표 ROAS (기본값 5.0)
API_PORT=8000
```

> API 키 미설정 시 자동으로 샘플 데이터로 동작합니다.

---

## 테스트

```bash
uv run pytest               # 전체 테스트 (52개)
uv run pytest -v            # 상세 출력
uv run pytest tests/test_optimizer.py   # 특정 파일만
```

---

## 개발 로드맵

- [x] Phase 1 — FastAPI 기반 구축, OAuth 인증
- [x] Phase 2 — 리포트 수집 파이프라인
- [x] Phase 3 — ROAS 최적화 엔진 (분석)
- [x] Phase 4 — 대시보드 API + UI
- [ ] Phase 5 — 입찰가 자동 조정 (`PUT /sp/keywords`) ← API 키 수령 후
- [ ] Phase 5 — 네거티브 자동 등록 (`POST /sp/negativeKeywords`) ← API 키 수령 후
- [ ] Phase 5 — 4시간 주기 스케줄러 (APScheduler) ← API 키 수령 후
- [ ] Phase 6 — 액션 이력 DB 저장 (SQLite → PostgreSQL)
