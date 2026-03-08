---
name: check-status
description: 현재 ROAS 상태 빠른 확인. 캠페인별 성과, 목표 달성 여부, 즉시 조치 필요 항목을 요약 출력.
---

# Check ROAS Status

현재 광고 성과를 빠르게 확인하고 요약 리포트를 출력한다.

## 실행 방법

```bash
# 전체 요약 출력
uv run python -m app.routers.dashboard --status

# JSON 출력 (대시보드 API 응답 형태)
curl http://localhost:8000/dashboard/status
```

## 출력 항목
- 전체 ROAS / 목표 대비 달성률
- 캠페인별 ROAS 순위 (목표 달성 ✅ / 근접 ⚠️ / 미달 ❌)
- 즉시 조치 필요 항목 수 (네거티브 후보, 입찰 조정 대상)
- 마지막 최적화 실행 시각
- 이번 주 누적 광고비 / 매출 / ROAS 추이

## 예시 출력
```
=== ROAS 상태 요약 (2025-08-01 09:00) ===
전체 ROAS:  4.61  →  목표 5.0  (달성률 92%)
총 광고비:  $4,376  |  총 매출: $20,183

캠페인별:
  ✅ COMP_SP_ASIN_XS_Wickedpup  ROAS 6.04
  ✅ BDEF_SP_ALL                ROAS 5.95
  ⚠️  AUTO_SP_S                  ROAS 4.92
  ❌  AUTO_SP_XS                 ROAS 3.26

즉시 조치 필요:
  - 네거티브 추가 대상: 24건  ($184 절감 가능)
  - 입찰 인하 대상: 27건
  - 입찰 인상 대상: 21건

마지막 최적화: 2025-08-01 06:00 (3시간 전)
```
