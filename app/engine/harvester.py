import logging

from app.config import settings
from app.models.schemas import ActionType, KeywordMetrics, OptimizationAction

logger = logging.getLogger(__name__)

_HARVEST_MATCH_TYPES = {"BROAD", "AUTO", "-"}   # Auto 캠페인은 "-" 로 표기됨


def find_harvest_candidates(
    metrics: list[KeywordMetrics],
    min_orders: int = 2,
    min_clicks: int = 10,
) -> list[KeywordMetrics]:
    """
    Auto / Broad 캠페인에서 Exact로 수확할 검색어 반환.

    조건:
      - match_type이 BROAD 또는 AUTO(-)
      - 주문 ≥ min_orders
      - 클릭 ≥ min_clicks
    """
    candidates = [
        kw for kw in metrics
        if kw.match_type.upper() in _HARVEST_MATCH_TYPES
        and kw.orders >= min_orders
        and kw.clicks >= min_clicks
    ]

    logger.info("Harvest candidates: %d keywords", len(candidates))
    return sorted(candidates, key=lambda kw: kw.sales, reverse=True)


def tag_harvest_actions(
    actions: list[OptimizationAction],
    min_orders: int = 2,
    min_clicks: int = 10,
) -> list[OptimizationAction]:
    """
    기존 OptimizationAction 리스트에서 수확 대상을 찾아
    action을 HARVEST_TO_EXACT로 업데이트하여 반환.
    """
    updated: list[OptimizationAction] = []

    for action in actions:
        kw = action.keyword
        is_harvest = (
            kw.match_type.upper() in _HARVEST_MATCH_TYPES
            and kw.orders >= min_orders
            and kw.clicks >= min_clicks
        )

        if is_harvest and action.action not in (
            ActionType.NEGATIVE_CANDIDATE,
            ActionType.INSUFFICIENT_DATA,
        ):
            updated.append(action.model_copy(update={
                "action": ActionType.HARVEST_TO_EXACT,
                "reason": (
                    f"Orders={kw.orders} Clicks={kw.clicks} "
                    f"ROAS={kw.roas:.2f} — move to Exact campaign"
                ),
            }))
            logger.debug("Harvest tagged: %s (orders=%d)", kw.search_term, kw.orders)
        else:
            updated.append(action)

    return updated
