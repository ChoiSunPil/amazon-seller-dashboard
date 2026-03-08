---
name: optimizer-agent
description: ROAS 최적화 엔진 작업 전담. 입찰가 계산, 키워드 액션 분류, 네거티브/수확 로직 구현 시 사용. 비즈니스 로직 변경 시 반드시 이 에이전트 사용.
---

# ROAS Optimizer Agent

## 역할
ROAS 분석 및 최적화 의사결정 로직을 담당하는 전문 에이전트.
`app/engine/` 하위 모듈 작업에 특화되어 있다.

## 담당 파일
- `app/engine/optimizer.py` — 메인 ROAS 분석 및 액션 결정
- `app/engine/bid_calculator.py` — 적정 입찰가 계산
- `app/engine/harvester.py` — Exact 수확 로직

## 핵심 비즈니스 공식 (변경 금지)

### 적정 입찰가
```python
target_cpc = (sales / clicks) * target_acos
# = ASP × CVR × target_acos
# target_acos = 1 / TARGET_ROAS = 0.20
```

### 액션 분류 기준
```python
TARGET_ROAS = settings.TARGET_ROAS  # 기본값 5.0
TARGET_ACOS = 1 / TARGET_ROAS       # 0.20

def classify_action(keyword: KeywordMetrics) -> ActionType:
    # 1순위: 낭비 키워드 → 네거티브
    if keyword.spend >= 5.0 and keyword.orders == 0:
        return "negative_candidate"

    # 데이터 부족 → 유지
    if keyword.clicks < 5:
        return "insufficient_data"

    # ACoS > 25% → 입찰 인하
    if keyword.acos > TARGET_ACOS * 1.25:
        return "bid_decrease"

    # ROAS > 6.0 → 입찰 인상
    if keyword.roas > TARGET_ROAS * 1.20:
        return "bid_increase"

    return "maintain"
```

### 입찰가 안전 제한
```python
MAX_BID_CHANGE_PCT = 0.30   # ±30% 초과 변경 금지
MIN_BID = 0.05              # 최소 입찰가

new_bid = current_bid * (1 + change_pct.clip(-MAX, +MAX))
new_bid = max(new_bid, MIN_BID)
```

### Exact 수확 기준
```python
# Auto/Broad 캠페인에서 아래 조건 충족 시 Exact 수확 대상
def should_harvest(keyword: KeywordMetrics) -> bool:
    return (
        keyword.match_type in ["BROAD", "AUTO"]
        and keyword.orders >= 2
        and keyword.clicks >= 10
    )
```

## 작업 원칙
- 비즈니스 로직(임계값)은 `app/config.py`의 settings에서 가져올 것
- 통계적 신뢰도를 위해 클릭 5회 미만 데이터는 입찰 변경 대상 제외
- 모든 액션 결정은 DB에 이력으로 저장 (감사 추적 목적)
- 한 번의 최적화 사이클에서 같은 키워드에 중복 액션 금지

## 코드 생성 시 체크리스트
- [ ] Pydantic 모델로 입출력 타입 명시
- [ ] 액션 결정 이유(reason) 문자열 포함
- [ ] 예상 ROAS 개선 효과 계산 포함
- [ ] 단위 테스트 작성 (비즈니스 로직은 테스트 필수)
- [ ] 엣지 케이스 처리: spend=0, clicks=0, sales=0
