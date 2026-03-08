"""
API 없이 실행 가능한 파싱 로직 단위 테스트.
실제 Amazon API 호출 없이 parse_search_term_records() 검증.
"""
import pytest
from app.api.reports import parse_search_term_records
from app.models.schemas import KeywordMetrics


# ── 샘플 데이터 (Amazon API 응답 형태) ──────────────────────────

SAMPLE_RECORDS = [
    {
        "campaignName": "KY_SP_S_liners",
        "adGroupName":  "Exact-S",
        "searchTerm":   "dog diaper liners",
        "targeting":    "dog diaper liners",
        "matchType":    "EXACT",
        "impressions":  12790,
        "clicks":       97,
        "cost":         163.64,
        "sales7d":      653.75,
        "purchases7d":  25,
        "purchasesPromotedUnits7d": 25,
        "costPerClick": 1.69,
    },
    {
        "campaignName": "AUTO_SP_S",
        "adGroupName":  "Auto",
        "searchTerm":   "belly band for dogs",
        "targeting":    "close-match",
        "matchType":    "",
        "impressions":  500,
        "clicks":       3,
        "cost":         5.50,
        "sales7d":      0,       # 주문 없음 → negative 후보
        "purchases7d":  0,
        "purchasesPromotedUnits7d": 0,
        "costPerClick": 1.50,
    },
    {
        # 결측 필드 있는 불량 데이터 — 파싱 실패 없이 스킵해야 함
        "campaignName": "KY_SP_ALL_Test",
        "clicks":       "invalid",   # 잘못된 타입
    },
]


# ── 테스트 ──────────────────────────────────────────────────────

def test_parse_returns_list_of_keyword_metrics():
    result = parse_search_term_records(SAMPLE_RECORDS)
    assert isinstance(result, list)
    assert all(isinstance(r, KeywordMetrics) for r in result)


def test_parse_skips_malformed_rows():
    """불량 데이터 행은 스킵하고 나머지는 정상 파싱"""
    result = parse_search_term_records(SAMPLE_RECORDS)
    assert len(result) == 2  # 불량 1건 제외


def test_roas_computed_correctly():
    result = parse_search_term_records(SAMPLE_RECORDS)
    kw = result[0]
    expected_roas = round(653.75 / 163.64, 4)
    assert kw.roas == expected_roas


def test_acos_computed_correctly():
    result = parse_search_term_records(SAMPLE_RECORDS)
    kw = result[0]
    expected_acos = round(163.64 / 653.75, 4)
    assert kw.acos == expected_acos


def test_cvr_computed_correctly():
    result = parse_search_term_records(SAMPLE_RECORDS)
    kw = result[0]
    expected_cvr = round(25 / 97, 4)
    assert kw.cvr == expected_cvr


def test_zero_spend_roas_is_zero():
    """광고비 0이면 ROAS 0 (ZeroDivisionError 없어야 함)"""
    records = [{
        "campaignName": "TEST", "adGroupName": "AG", "searchTerm": "test",
        "impressions": 10, "clicks": 0, "cost": 0,
        "sales7d": 0, "purchases7d": 0,
        "purchasesPromotedUnits7d": 0, "costPerClick": 0,
    }]
    result = parse_search_term_records(records)
    assert result[0].roas == 0.0
    assert result[0].acos == 0.0
    assert result[0].cvr  == 0.0


def test_zero_order_keywords_identified():
    """주문 0건 키워드 필터링 가능한지 확인"""
    result   = parse_search_term_records(SAMPLE_RECORDS)
    no_order = [kw for kw in result if kw.orders == 0 and kw.spend >= 5.0]
    assert len(no_order) == 1
    assert no_order[0].search_term == "belly band for dogs"


def test_asp_is_zero_when_no_orders():
    result = parse_search_term_records(SAMPLE_RECORDS)
    kw_no_order = next(kw for kw in result if kw.orders == 0)
    assert kw_no_order.asp == 0.0
