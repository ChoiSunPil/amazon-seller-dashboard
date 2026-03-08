import logging

from app.config import settings
from app.engine.bid_calculator import calculate_target_cpc
from app.models.schemas import (
    ActionType,
    KeywordMetrics,
    OptimizationAction,
    OptimizationSummary,
)

logger = logging.getLogger(__name__)


def classify_action(kw: KeywordMetrics) -> tuple[ActionType, str]:
    """
    키워드 성과 지표 → 액션 분류 + 사유 반환.

    우선순위:
      1. 낭비 키워드 (주문=0, 광고비≥$5)  → negative_candidate
      2. 데이터 부족 (클릭<5)             → insufficient_data
      3. ACoS > 목표×1.25 (>25%)         → bid_decrease
      4. ROAS > 목표×1.20 (>6.0)         → bid_increase
      5. 그 외                            → maintain
    """
    target_acos = settings.target_acos
    target_roas = settings.target_roas

    if kw.spend >= settings.min_spend_negative and kw.orders == 0:
        return (
            ActionType.NEGATIVE_CANDIDATE,
            f"Spend ${kw.spend:.2f} with 0 orders — wasted budget",
        )

    if kw.clicks < settings.min_clicks_for_bid:
        return (
            ActionType.INSUFFICIENT_DATA,
            f"Only {kw.clicks} clicks — need ≥{settings.min_clicks_for_bid} for reliable bid change",
        )

    if kw.acos > target_acos * 1.25:
        return (
            ActionType.BID_DECREASE,
            f"ACoS {kw.acos:.1%} > threshold {target_acos*1.25:.1%} — reduce bid",
        )

    if kw.roas > target_roas * 1.20:
        return (
            ActionType.BID_INCREASE,
            f"ROAS {kw.roas:.2f} > threshold {target_roas*1.20:.2f} — scale up",
        )

    return (
        ActionType.MAINTAIN,
        f"ROAS {kw.roas:.2f} within target range — maintain",
    )


def build_optimization_actions(
    metrics: list[KeywordMetrics],
    global_asp: float = 0.0,
) -> list[OptimizationAction]:
    """
    KeywordMetrics 리스트 전체를 분석하여 OptimizationAction 리스트 반환.
    global_asp: 전체 평균 판매가 (데이터 부족 키워드의 입찰가 추산에 사용)
    """
    actions: list[OptimizationAction] = []

    for kw in metrics:
        action_type, reason = classify_action(kw)
        target_bid = calculate_target_cpc(kw, global_asp)

        actions.append(OptimizationAction(
            keyword=kw,
            action=action_type,
            current_bid=kw.cpc,
            target_bid=target_bid,
            reason=reason,
        ))

        logger.debug(
            "[%s] %s | ROAS=%.2f ACoS=%.1%% → %s",
            kw.campaign_name, kw.search_term,
            kw.roas, kw.acos * 100, action_type.value,
        )

    _log_summary(actions)
    return actions


def summarize(actions: list[OptimizationAction]) -> OptimizationSummary:
    """액션 리스트 → 전체 최적화 사이클 요약."""
    from collections import Counter
    counts = Counter(a.action for a in actions)

    total_spend = sum(a.keyword.spend for a in actions)
    total_sales = sum(a.keyword.sales for a in actions)

    return OptimizationSummary(
        total_keywords    = len(actions),
        bid_increase      = counts[ActionType.BID_INCREASE],
        bid_decrease      = counts[ActionType.BID_DECREASE],
        negative_added    = counts[ActionType.NEGATIVE_CANDIDATE],
        harvest_to_exact  = counts[ActionType.HARVEST_TO_EXACT],
        maintain          = counts[ActionType.MAINTAIN],
        insufficient_data = counts[ActionType.INSUFFICIENT_DATA],
        total_spend       = round(total_spend, 2),
        total_sales       = round(total_sales, 2),
    )


def _log_summary(actions: list[OptimizationAction]) -> None:
    summary = summarize(actions)
    logger.info(
        "Optimization summary | total=%d | ROAS=%.2f | "
        "bid↑=%d bid↓=%d negative=%d harvest=%d maintain=%d insufficient=%d",
        summary.total_keywords, summary.overall_roas,
        summary.bid_increase, summary.bid_decrease,
        summary.negative_added, summary.harvest_to_exact,
        summary.maintain, summary.insufficient_data,
    )
