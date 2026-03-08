---
name: fetch-report
description: Amazon Advertising API에서 리포트를 요청하고 다운로드. 특정 날짜 범위의 Search Term / Targeting 리포트 수동 수집 시 사용.
---

# Fetch Amazon Report

Amazon Advertising API를 통해 리포트를 요청하고 로컬에 저장한다.

## 실행 방법

```bash
# 어제 기준 Search Term 리포트 수집
uv run python -m app.api.reports --type search_term --date yesterday

# 특정 날짜 범위
uv run python -m app.api.reports --type search_term --start 2025-06-01 --end 2025-06-30

# Targeting 리포트
uv run python -m app.api.reports --type targeting --date yesterday

# 두 리포트 동시 수집
uv run python -m app.api.reports --type all --date yesterday
```

## 리포트 저장 경로
```
data/reports/
├── search_term_YYYYMMDD.csv
└── targeting_YYYYMMDD.csv
```

## 구현 시 참고 (api-agent 활용)
1. `POST /reporting/reports` 로 리포트 생성 요청
2. 반환된 `reportId` 로 상태 폴링 (30초 간격, 최대 10분)
3. `status == COMPLETED` → `downloadUrl` 로 gzip 다운로드
4. 압축 해제 후 CSV 파싱
5. `data/reports/` 에 날짜별 저장
