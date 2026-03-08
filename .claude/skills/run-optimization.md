---
name: run-optimization
description: ROAS 최적화 사이클 전체 실행. 리포트 수집 → 분석 → 액션 적용까지 한 번에 처리.
---

# Run Optimization Cycle

전체 ROAS 최적화 파이프라인을 실행한다.

## 실행 순서

1. **리포트 수집** — Amazon API에서 최신 Search Term + Targeting 리포트 요청
2. **데이터 파싱** — CSV 파싱 후 KeywordMetrics 모델로 변환
3. **ROAS 분석** — optimizer-agent 활용하여 각 키워드 액션 분류
4. **액션 실행**
   - `bid_increase` / `bid_decrease` → `PUT /sp/keywords` 배치 전송
   - `negative_candidate` → `POST /sp/negativeKeywords` 배치 전송
   - `harvest_to_exact` → 수확 목록 저장 (수동 검토 후 적용)
5. **결과 저장** — 액션 이력 DB 저장 + 요약 로그 출력

## 사용 방법

```bash
# 전체 최적화 사이클 실행
uv run python -m app.engine.optimizer --run

# 드라이런 (실제 API 변경 없이 분석만)
uv run python -m app.engine.optimizer --dry-run

# 특정 캠페인만 실행
uv run python -m app.engine.optimizer --campaign KY_SP_S_liners
```

## 주의사항
- 드라이런(`--dry-run`) 먼저 실행하여 액션 목록 확인 후 실제 적용 권장
- 하루 2회 이상 실행 시 동일 키워드 중복 처리 주의
- 입찰 변경 후 최소 7일 데이터 축적 후 재조정
