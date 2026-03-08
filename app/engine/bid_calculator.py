import logging

from app.config import settings
from app.models.schemas import KeywordMetrics

logger = logging.getLogger(__name__)


def calculate_target_cpc(kw: KeywordMetrics, global_asp: float = 0.0) -> float:
    """
    목표 ROAS 기반 적정 입찰가 계산.

    공식: target_cpc = ASP × CVR × target_acos
                     = (sales / clicks) × target_acos

    데이터 부족(클릭 < 5)이면 현재 CPC 그대로 반환.
    """
    if kw.clicks < settings.min_clicks_for_bid:
        return kw.cpc

    if kw.clicks > 0 and kw.sales > 0:
        # 실측 데이터 기반
        target_cpc = (kw.sales / kw.clicks) * settings.target_acos
    else:
        # 실측 불가 → 글로벌 ASP + CVR 0으로 추산 (사실상 최소값 적용)
        asp = global_asp or kw.asp
        target_cpc = asp * kw.cvr * settings.target_acos

    return _apply_safety_limits(target_cpc, kw.cpc)


def _apply_safety_limits(target_cpc: float, current_cpc: float) -> float:
    """1회 변경폭 ±30% 제한 및 최소 입찰가 보장."""
    if current_cpc <= 0:
        return max(target_cpc, settings.min_bid)

    max_allowed = current_cpc * (1 + settings.max_bid_change_pct)
    min_allowed = current_cpc * (1 - settings.max_bid_change_pct)

    clamped = max(min_allowed, min(target_cpc, max_allowed))
    return round(max(clamped, settings.min_bid), 2)
