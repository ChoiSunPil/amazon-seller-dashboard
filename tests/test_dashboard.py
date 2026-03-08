"""
tests/test_dashboard.py
대시보드 API 엔드포인트 테스트.

샘플 데이터(하드코딩 fallback)로 실행되므로 API 키 없이도 동작.
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from main import app
from app.models.schemas import KeywordMetrics


# ── 공통 샘플 메트릭 ────────────────────────────────────────────────

def _sample_metrics() -> list[KeywordMetrics]:
    return [
        KeywordMetrics(
            campaign_name="Camp_A",
            ad_group_name="AG_Exact",
            search_term="dog diaper liners",
            match_type="EXACT",
            impressions=10000,
            clicks=100,
            spend=120.0,
            sales=720.0,
            orders=30,
            cpc=1.20,
        ),
        KeywordMetrics(
            campaign_name="Camp_A",
            ad_group_name="AG_Broad",
            search_term="dog diaper liners",
            match_type="BROAD",
            impressions=12000,
            clicks=200,
            spend=300.0,
            sales=1500.0,
            orders=60,
            cpc=1.50,
        ),
        KeywordMetrics(
            campaign_name="Camp_B",
            ad_group_name="AG_Auto",
            search_term="disposable dog diapers",
            match_type="",
            impressions=5000,
            clicks=40,
            spend=60.0,
            sales=0.0,
            orders=0,
            cpc=1.50,
        ),
        KeywordMetrics(
            campaign_name="Camp_C",
            ad_group_name="AG_Exact2",
            search_term="female dog diapers",
            match_type="EXACT",
            impressions=8000,
            clicks=80,
            spend=80.0,
            sales=600.0,
            orders=25,
            cpc=1.00,
        ),
    ]


# ── 픽스처: _get_metrics 를 항상 샘플로 패치 ────────────────────────

@pytest.fixture
def client():
    """TestClient with _get_metrics patched to return sample data."""
    with patch(
        "app.routers.dashboard._get_metrics",
        new=AsyncMock(return_value=_sample_metrics()),
    ):
        with TestClient(app) as c:
            yield c


# ── /dashboard/status ───────────────────────────────────────────────

class TestStatus:
    def test_status_returns_200(self, client):
        resp = client.get("/dashboard/status")
        assert resp.status_code == 200

    def test_status_contains_required_keys(self, client):
        data = client.get("/dashboard/status").json()
        for key in ("overall_roas", "overall_acos_pct", "target_roas",
                    "target_achieved_pct", "roas_gap", "total_spend",
                    "total_sales", "total_keywords", "actions_needed", "data_source"):
            assert key in data, f"Missing key: {key}"

    def test_status_roas_calculation(self, client):
        data = client.get("/dashboard/status").json()
        # spend=120+300+60+80=560, sales=720+1500+0+600=2820 → ROAS = 2820/560 ≈ 5.04
        assert data["overall_roas"] == pytest.approx(5.04, abs=0.01)

    def test_status_target_roas(self, client):
        data = client.get("/dashboard/status").json()
        assert data["target_roas"] == pytest.approx(5.0, abs=0.01)

    def test_status_roas_gap_sign(self, client):
        data = client.get("/dashboard/status").json()
        # ROAS > 5.0 → gap should be negative (overachieving)
        assert data["roas_gap"] < 0

    def test_status_data_source_is_sample(self, client):
        data = client.get("/dashboard/status").json()
        assert data["data_source"] == "sample"

    def test_status_actions_needed_structure(self, client):
        data = client.get("/dashboard/status").json()
        actions = data["actions_needed"]
        assert "bid_increase" in actions
        assert "bid_decrease" in actions
        assert "negative_candidate" in actions
        assert "harvest_to_exact" in actions


# ── /dashboard/campaigns ────────────────────────────────────────────

class TestCampaigns:
    def test_campaigns_returns_200(self, client):
        resp = client.get("/dashboard/campaigns")
        assert resp.status_code == 200

    def test_campaigns_returns_list(self, client):
        data = client.get("/dashboard/campaigns").json()
        assert isinstance(data, list)

    def test_campaigns_count(self, client):
        data = client.get("/dashboard/campaigns").json()
        # Camp_A, Camp_B, Camp_C → 3 campaigns
        assert len(data) == 3

    def test_campaigns_contains_required_keys(self, client):
        data = client.get("/dashboard/campaigns").json()
        for camp in data:
            for key in ("campaign_name", "spend", "sales", "orders",
                        "clicks", "roas", "acos_pct", "status"):
                assert key in camp, f"Missing key: {key}"

    def test_campaigns_sorted_by_spend_desc(self, client):
        data = client.get("/dashboard/campaigns").json()
        spends = [c["spend"] for c in data]
        assert spends == sorted(spends, reverse=True)

    def test_campaigns_status_labels(self, client):
        data = client.get("/dashboard/campaigns").json()
        valid_statuses = {"achieved", "close", "underperforming"}
        for camp in data:
            assert camp["status"] in valid_statuses

    def test_camp_b_underperforming(self, client):
        """Camp_B: sales=0, ROAS=0 → underperforming"""
        data = client.get("/dashboard/campaigns").json()
        camp_b = next(c for c in data if c["campaign_name"] == "Camp_B")
        assert camp_b["status"] == "underperforming"
        assert camp_b["roas"] == 0.0


# ── /dashboard/actions ──────────────────────────────────────────────

class TestActions:
    def test_actions_returns_200(self, client):
        resp = client.get("/dashboard/actions")
        assert resp.status_code == 200

    def test_actions_returns_list(self, client):
        data = client.get("/dashboard/actions").json()
        assert isinstance(data, list)

    def test_actions_contains_required_keys(self, client):
        data = client.get("/dashboard/actions").json()
        for action in data:
            for key in ("search_term", "campaign_name", "match_type",
                        "clicks", "orders", "spend", "sales",
                        "roas", "acos_pct", "current_bid", "target_bid",
                        "bid_change_pct", "action", "reason"):
                assert key in action, f"Missing key: {key}"

    def test_actions_filter_by_negative_candidate(self, client):
        data = client.get("/dashboard/actions?action_type=negative_candidate").json()
        for action in data:
            assert action["action"] == "negative_candidate"

    def test_actions_filter_invalid_type_returns_400(self, client):
        resp = client.get("/dashboard/actions?action_type=invalid_type")
        assert resp.status_code == 400

    def test_actions_filter_by_min_spend(self, client):
        data = client.get("/dashboard/actions?min_spend=100").json()
        for action in data:
            assert action["spend"] >= 100.0

    def test_actions_sorted_by_spend_desc(self, client):
        data = client.get("/dashboard/actions").json()
        spends = [a["spend"] for a in data]
        assert spends == sorted(spends, reverse=True)

    def test_camp_b_identified_as_negative_candidate(self, client):
        """Camp_B / Auto: orders=0, spend=$60 > $5 → negative_candidate"""
        data = client.get("/dashboard/actions?action_type=negative_candidate").json()
        terms = [a["search_term"] for a in data]
        assert "disposable dog diapers" in terms


# ── /dashboard/harvest ──────────────────────────────────────────────

class TestHarvest:
    def test_harvest_returns_200(self, client):
        resp = client.get("/dashboard/harvest")
        assert resp.status_code == 200

    def test_harvest_returns_list(self, client):
        data = client.get("/dashboard/harvest").json()
        assert isinstance(data, list)

    def test_harvest_contains_required_keys(self, client):
        data = client.get("/dashboard/harvest").json()
        for kw in data:
            for key in ("search_term", "campaign_name", "match_type",
                        "clicks", "orders", "cvr_pct", "spend", "sales", "roas"):
                assert key in kw, f"Missing key: {key}"

    def test_harvest_only_broad_auto(self, client):
        """수확 후보는 BROAD / AUTO / '-' 매치 타입만."""
        data = client.get("/dashboard/harvest").json()
        allowed = {"BROAD", "AUTO", "", "-"}
        for kw in data:
            assert kw["match_type"].upper() in allowed or kw["match_type"] == ""

    def test_harvest_broad_term_included(self, client):
        """BROAD / 주문 60 / 클릭 200 → 수확 후보 포함"""
        data = client.get("/dashboard/harvest").json()
        found = any(
            kw["search_term"] == "dog diaper liners" and kw["match_type"] == "BROAD"
            for kw in data
        )
        assert found

    def test_harvest_sorted_by_sales_desc(self, client):
        data = client.get("/dashboard/harvest").json()
        if len(data) >= 2:
            sales = [kw["sales"] for kw in data]
            assert sales == sorted(sales, reverse=True)
