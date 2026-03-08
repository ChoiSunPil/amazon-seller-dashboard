"""
최적화 엔진 단위 테스트.
Amazon API 호출 없이 비즈니스 로직만 검증.
"""
import pytest
from app.models.schemas import ActionType, KeywordMetrics
from app.engine.optimizer import classify_action, build_optimization_actions, summarize
from app.engine.bid_calculator import calculate_target_cpc
from app.engine.harvester import find_harvest_candidates, tag_harvest_actions


# ── 픽스처 헬퍼 ────────────────────────────────────────────────

def make_kw(**kwargs) -> KeywordMetrics:
    defaults = dict(
        campaign_name="TEST_CAMP", ad_group_name="AG",
        search_term="dog diaper liners", match_type="EXACT",
        impressions=1000, clicks=50, spend=100.0,
        sales=500.0, orders=20, cpc=2.0,
    )
    defaults.update(kwargs)
    return KeywordMetrics(**defaults)


# ── classify_action 테스트 ─────────────────────────────────────

def test_negative_candidate_when_spend_above_threshold_and_no_orders():
    kw = make_kw(spend=10.0, orders=0, clicks=6)
    action, reason = classify_action(kw)
    assert action == ActionType.NEGATIVE_CANDIDATE
    assert "0 orders" in reason


def test_insufficient_data_when_clicks_below_threshold():
    kw = make_kw(clicks=4, orders=0, spend=3.0)
    action, _ = classify_action(kw)
    assert action == ActionType.INSUFFICIENT_DATA


def test_bid_decrease_when_acos_above_threshold():
    # ACoS > 25% → bid_decrease
    # spend=100, sales=300 → ACoS=33%
    kw = make_kw(clicks=20, spend=100.0, sales=300.0, orders=10)
    action, reason = classify_action(kw)
    assert action == ActionType.BID_DECREASE
    assert "reduce bid" in reason


def test_bid_increase_when_roas_above_threshold():
    # ROAS > 6.0 → bid_increase
    # spend=100, sales=700 → ROAS=7.0
    kw = make_kw(clicks=20, spend=100.0, sales=700.0, orders=25)
    action, reason = classify_action(kw)
    assert action == ActionType.BID_INCREASE
    assert "scale up" in reason


def test_maintain_when_within_target_range():
    # spend=100, sales=500 → ROAS=5.0 → maintain
    kw = make_kw(clicks=20, spend=100.0, sales=500.0, orders=18)
    action, _ = classify_action(kw)
    assert action == ActionType.MAINTAIN


def test_negative_takes_priority_over_bid_rules():
    """주문=0, 광고비≥$5 이면 ACoS와 무관하게 네거티브 우선"""
    kw = make_kw(clicks=20, spend=50.0, sales=0.0, orders=0)
    action, _ = classify_action(kw)
    assert action == ActionType.NEGATIVE_CANDIDATE


# ── calculate_target_cpc 테스트 ────────────────────────────────

def test_target_cpc_basic():
    # sales=500, clicks=50, target_acos=0.20 → target_cpc = 500/50 * 0.20 = 2.00
    kw = make_kw(clicks=50, spend=100.0, sales=500.0, cpc=2.0)
    result = calculate_target_cpc(kw)
    assert result == 2.00


def test_target_cpc_clamped_to_max_increase():
    # 현재 cpc=1.0, 목표가 $2.0이면 최대 30% 인상 → $1.30
    kw = make_kw(clicks=50, spend=50.0, sales=1000.0, cpc=1.0)
    result = calculate_target_cpc(kw)
    assert result == round(1.0 * 1.30, 2)


def test_target_cpc_clamped_to_max_decrease():
    # 현재 cpc=3.0, 목표가 $0.50이면 최대 30% 인하 → $2.10
    kw = make_kw(clicks=50, spend=150.0, sales=100.0, cpc=3.0)
    result = calculate_target_cpc(kw)
    assert result == round(3.0 * 0.70, 2)


def test_target_cpc_minimum_bid():
    # 계산 결과가 $0.05 미만이어도 최소 $0.05 보장
    kw = make_kw(clicks=50, spend=100.0, sales=1.0, orders=0, cpc=0.05)
    result = calculate_target_cpc(kw)
    assert result >= 0.05


def test_target_cpc_returns_current_when_insufficient_clicks():
    kw = make_kw(clicks=3, cpc=1.50)
    result = calculate_target_cpc(kw)
    assert result == 1.50  # 클릭 부족 → 현재값 유지


# ── harvester 테스트 ───────────────────────────────────────────

def test_harvest_candidates_broad():
    kw = make_kw(match_type="BROAD", orders=3, clicks=15)
    result = find_harvest_candidates([kw])
    assert len(result) == 1


def test_harvest_candidates_auto():
    kw = make_kw(match_type="-", orders=5, clicks=20)
    result = find_harvest_candidates([kw])
    assert len(result) == 1


def test_harvest_excludes_exact():
    kw = make_kw(match_type="EXACT", orders=5, clicks=20)
    result = find_harvest_candidates([kw])
    assert len(result) == 0


def test_harvest_requires_min_orders():
    kw = make_kw(match_type="BROAD", orders=1, clicks=20)
    result = find_harvest_candidates([kw])
    assert len(result) == 0


def test_harvest_requires_min_clicks():
    kw = make_kw(match_type="BROAD", orders=5, clicks=5)
    result = find_harvest_candidates([kw])
    assert len(result) == 0


def test_harvest_sorted_by_sales_desc():
    kw_low  = make_kw(match_type="BROAD", orders=3, clicks=15, sales=100.0, search_term="kw_low")
    kw_high = make_kw(match_type="BROAD", orders=5, clicks=20, sales=500.0, search_term="kw_high")
    result  = find_harvest_candidates([kw_low, kw_high])
    assert result[0].search_term == "kw_high"


# ── 통합: build_optimization_actions + summarize ───────────────

def test_summary_counts_match_actions():
    metrics = [
        make_kw(search_term="kw1", clicks=20, spend=100.0, sales=700.0, orders=25),  # bid_increase
        make_kw(search_term="kw2", clicks=20, spend=100.0, sales=300.0, orders=10),  # bid_decrease
        make_kw(search_term="kw3", clicks=6,  spend=10.0,  sales=0.0,   orders=0),   # negative
        make_kw(search_term="kw4", clicks=3,  spend=2.0,   sales=0.0,   orders=0),   # insufficient
        make_kw(search_term="kw5", clicks=20, spend=100.0, sales=500.0, orders=18),  # maintain
    ]
    actions = build_optimization_actions(metrics)
    summary = summarize(actions)

    assert summary.total_keywords    == 5
    assert summary.bid_increase      == 1
    assert summary.bid_decrease      == 1
    assert summary.negative_added    == 1
    assert summary.insufficient_data == 1
    assert summary.maintain          == 1


def test_summary_overall_roas():
    metrics = [
        make_kw(spend=100.0, sales=500.0),
        make_kw(spend=100.0, sales=500.0),
    ]
    actions = build_optimization_actions(metrics)
    summary = summarize(actions)
    assert summary.overall_roas == 5.0
