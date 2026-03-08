import logging
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.engine.harvester import find_harvest_candidates, tag_harvest_actions
from app.engine.optimizer import build_optimization_actions, summarize
from app.models.schemas import (
    ActionType,
    KeywordMetrics,
    OptimizationAction,
    OptimizationSummary,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ── 샘플 데이터 로더 (API 키 없을 때 CSV 기반으로 동작) ─────────────

def _load_sample_metrics() -> list[KeywordMetrics]:
    """
    .env에 API 키가 없으면 data/sample/ CSV로 fallback.
    API 키 세팅 후에는 app/api/reports.py 의 fetch_search_term_report() 로 대체.
    """
    import csv
    from pathlib import Path

    sample_path = Path("data/sample/search_term.csv")
    if not sample_path.exists():
        return _get_hardcoded_sample()

    metrics: list[KeywordMetrics] = []
    with sample_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                metrics.append(KeywordMetrics(
                    campaign_name = row.get("Campaign Name", ""),
                    ad_group_name = row.get("Ad Group Name", ""),
                    search_term   = row.get("Customer Search Term", ""),
                    match_type    = row.get("Match Type", ""),
                    impressions   = int(float(row.get("Impressions", 0))),
                    clicks        = int(float(row.get("Clicks", 0))),
                    spend         = float(row.get("Spend", 0)),
                    sales         = float(row.get("7 Day Total Sales", 0)),
                    orders        = int(float(row.get("7 Day Total Orders (#)", 0))),
                    cpc           = float(row.get("Cost Per Click (CPC)", 0)),
                ))
            except Exception:
                continue
    return metrics


def _get_hardcoded_sample() -> list[KeywordMetrics]:
    """CSV도 없을 때를 위한 인메모리 샘플 (데모용)"""
    raw = [
        ("KY_SP_S_liners",            "Exact-S",  "dog diaper liners",          "EXACT",  12790, 97,  163.64, 653.75, 25, 1.69),
        ("KY_SP_S_New",               "Exact-New", "pawpang disposable liners",  "EXACT",  8200,  65,  89.11,  858.67, 33, 1.37),
        ("AUTO_SP_S",                 "Auto",      "disposable dog diapers female","",     5400,  40,  51.98,  339.87, 13, 1.30),
        ("AUTO_SP_S",                 "Auto",      "dog diapers male",           "",       3200,  43,  43.76,  317.88, 11, 1.02),
        ("KY_SP_ALL_Test",            "Exact-All", "reusable dog diapers female","EXACT",  9800,  105, 117.46, 524.80, 20, 1.12),
        ("KY_SP_S_New",               "Exact-New", "diapers for dogs male",      "EXACT",  2100,  45,  61.29,  78.97,  3,  1.36),
        ("AUTO_SP_XS",                "Auto",      "belly band for male dogs",   "",       800,   6,   7.20,   0.0,    0,  1.20),
        ("COMP_SP_ASIN_XS_Wickedpup", "ASIN",      "b092lvbpjg",                "-",      14200, 221, 243.37, 1385.46,54, 1.10),
        ("BDEF_SP_ALL",               "Auto",      "b0czdqvhy3",                "-",      6100,  69,  110.52, 674.74, 25, 1.60),
        ("KY_SP_S_liners",            "Broad-S",   "dog diaper liners",          "BROAD",  13467, 311, 579.81, 2738.95,105,1.87),
    ]
    return [
        KeywordMetrics(
            campaign_name=r[0], ad_group_name=r[1], search_term=r[2],
            match_type=r[3], impressions=r[4], clicks=r[5],
            spend=r[6], sales=r[7], orders=r[8], cpc=r[9],
        )
        for r in raw
    ]


async def _get_metrics() -> list[KeywordMetrics]:
    """API 키 유무에 따라 실시간 or 샘플 데이터 반환."""
    if settings.is_configured:
        from app.api.reports import fetch_search_term_report
        return await fetch_search_term_report()
    logger.warning("API not configured — using sample data")
    return _load_sample_metrics()


# ── 엔드포인트 ────────────────────────────────────────────────────

@router.get("/status", summary="전체 ROAS 현황 요약")
async def get_status() -> dict:
    """
    현재 광고 성과 요약.
    - 전체 ROAS / ACoS
    - 목표 대비 달성률
    - 액션 필요 건수
    """
    metrics = await _get_metrics()
    actions = build_optimization_actions(metrics)
    actions = tag_harvest_actions(actions)
    summary = summarize(actions)

    gap      = settings.target_roas - summary.overall_roas
    achieved = round(summary.overall_roas / settings.target_roas * 100, 1)

    return {
        "overall_roas":      summary.overall_roas,
        "overall_acos_pct":  summary.overall_acos_pct,
        "target_roas":       settings.target_roas,
        "target_achieved_pct": achieved,
        "roas_gap":          round(gap, 2),
        "total_spend":       summary.total_spend,
        "total_sales":       summary.total_sales,
        "total_keywords":    summary.total_keywords,
        "actions_needed": {
            "bid_increase":      summary.bid_increase,
            "bid_decrease":      summary.bid_decrease,
            "negative_candidate":summary.negative_added,
            "harvest_to_exact":  summary.harvest_to_exact,
        },
        "data_source": "live" if settings.is_configured else "sample",
    }


@router.get("/campaigns", summary="캠페인별 성과")
async def get_campaigns() -> list[dict]:
    """캠페인별 ROAS / ACoS / 광고비 / 매출 집계."""
    metrics = await _get_metrics()
    camp_map: dict[str, dict] = {}

    for kw in metrics:
        c = camp_map.setdefault(kw.campaign_name, {
            "campaign_name": kw.campaign_name,
            "spend": 0.0, "sales": 0.0, "orders": 0, "clicks": 0,
        })
        c["spend"]  += kw.spend
        c["sales"]  += kw.sales
        c["orders"] += kw.orders
        c["clicks"] += kw.clicks

    result = []
    for c in camp_map.values():
        roas = round(c["sales"] / c["spend"], 2) if c["spend"] > 0 else 0.0
        acos = round(c["spend"] / c["sales"] * 100, 1) if c["sales"] > 0 else 0.0
        result.append({
            **c,
            "spend":  round(c["spend"], 2),
            "sales":  round(c["sales"], 2),
            "roas":   roas,
            "acos_pct": acos,
            "status": "achieved" if roas >= settings.target_roas
                      else "close" if roas >= settings.target_roas * 0.8
                      else "underperforming",
        })

    return sorted(result, key=lambda x: x["spend"], reverse=True)


@router.get("/actions", summary="최적화 액션 목록")
async def get_actions(
    action_type: Optional[str] = Query(None, description="bid_increase | bid_decrease | negative_candidate | harvest_to_exact | maintain"),
    min_spend:   float         = Query(0.0,  description="최소 광고비 필터"),
) -> list[dict]:
    """
    최적화 엔진이 추천하는 전체 액션 목록.
    action_type / min_spend 으로 필터링 가능.
    """
    metrics = await _get_metrics()
    global_asp = (
        sum(kw.sales for kw in metrics) /
        sum(kw.orders for kw in metrics if kw.orders > 0)
        if any(kw.orders > 0 for kw in metrics) else 0.0
    )
    actions = build_optimization_actions(metrics, global_asp)
    actions = tag_harvest_actions(actions)

    # 필터
    if action_type:
        try:
            filter_type = ActionType(action_type)
            actions = [a for a in actions if a.action == filter_type]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown action_type: {action_type}")

    actions = [a for a in actions if a.keyword.spend >= min_spend]
    actions.sort(key=lambda a: a.keyword.spend, reverse=True)

    return [
        {
            "search_term":   a.keyword.search_term,
            "campaign_name": a.keyword.campaign_name,
            "match_type":    a.keyword.match_type,
            "clicks":        a.keyword.clicks,
            "orders":        a.keyword.orders,
            "spend":         round(a.keyword.spend, 2),
            "sales":         round(a.keyword.sales, 2),
            "roas":          a.keyword.roas,
            "acos_pct":      round(a.keyword.acos * 100, 1),
            "current_bid":   a.current_bid,
            "target_bid":    a.target_bid,
            "bid_change_pct":a.bid_change_pct,
            "action":        a.action.value,
            "reason":        a.reason,
        }
        for a in actions
    ]


@router.get("/harvest", summary="Exact 수확 후보 목록")
async def get_harvest() -> list[dict]:
    """Auto / Broad에서 Exact로 수확할 검색어 목록."""
    metrics    = await _get_metrics()
    candidates = find_harvest_candidates(metrics)

    return [
        {
            "search_term":   kw.search_term,
            "campaign_name": kw.campaign_name,
            "match_type":    kw.match_type,
            "clicks":        kw.clicks,
            "orders":        kw.orders,
            "cvr_pct":       round(kw.cvr * 100, 1),
            "spend":         round(kw.spend, 2),
            "sales":         round(kw.sales, 2),
            "roas":          kw.roas,
        }
        for kw in candidates
    ]
