from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, computed_field


# ─────────────────────────────────────────────────────────────
# 리포트 관련
# ─────────────────────────────────────────────────────────────

class ReportStatus(str, Enum):
    PENDING    = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED  = "COMPLETED"
    FAILED     = "FAILED"


class ReportType(str, Enum):
    SEARCH_TERM = "spSearchTerm"
    TARGETING   = "spTargeting"


class ReportResponse(BaseModel):
    report_id:    str = Field(alias="reportId")
    status:       ReportStatus
    download_url: Optional[str] = Field(None, alias="url")


# ─────────────────────────────────────────────────────────────
# 키워드 성과 지표
# ─────────────────────────────────────────────────────────────

class KeywordMetrics(BaseModel):
    """파싱된 검색어/키워드 단위 성과 지표"""

    campaign_name:  str
    ad_group_name:  str
    search_term:    str
    targeting:      str = ""
    match_type:     str = ""

    impressions: int   = 0
    clicks:      int   = 0
    spend:       float = 0.0
    sales:       float = 0.0
    orders:      int   = 0
    units:       int   = 0
    cpc:         float = 0.0

    @computed_field
    @property
    def roas(self) -> float:
        return round(self.sales / self.spend, 4) if self.spend > 0 else 0.0

    @computed_field
    @property
    def acos(self) -> float:
        return round(self.spend / self.sales, 4) if self.sales > 0 else 0.0

    @computed_field
    @property
    def cvr(self) -> float:
        return round(self.orders / self.clicks, 4) if self.clicks > 0 else 0.0

    @computed_field
    @property
    def asp(self) -> float:
        """평균 판매가 (Average Selling Price)"""
        return round(self.sales / self.orders, 2) if self.orders > 0 else 0.0

    @computed_field
    @property
    def ctr(self) -> float:
        return round(self.clicks / self.impressions, 4) if self.impressions > 0 else 0.0


# ─────────────────────────────────────────────────────────────
# 액션 결정
# ─────────────────────────────────────────────────────────────

class ActionType(str, Enum):
    BID_INCREASE       = "bid_increase"
    BID_DECREASE       = "bid_decrease"
    NEGATIVE_CANDIDATE = "negative_candidate"
    HARVEST_TO_EXACT   = "harvest_to_exact"
    MAINTAIN           = "maintain"
    INSUFFICIENT_DATA  = "insufficient_data"


class OptimizationAction(BaseModel):
    keyword:      KeywordMetrics
    action:       ActionType
    current_bid:  float
    target_bid:   float
    reason:       str

    @computed_field
    @property
    def bid_change_pct(self) -> float:
        if self.current_bid <= 0:
            return 0.0
        return round((self.target_bid - self.current_bid) / self.current_bid * 100, 1)


# ─────────────────────────────────────────────────────────────
# 최적화 사이클 요약
# ─────────────────────────────────────────────────────────────

class OptimizationSummary(BaseModel):
    total_keywords:    int
    bid_increase:      int
    bid_decrease:      int
    negative_added:    int
    harvest_to_exact:  int
    maintain:          int
    insufficient_data: int
    total_spend:       float
    total_sales:       float

    @computed_field
    @property
    def overall_roas(self) -> float:
        return round(self.total_sales / self.total_spend, 2) if self.total_spend > 0 else 0.0

    @computed_field
    @property
    def overall_acos_pct(self) -> float:
        return round(self.total_spend / self.total_sales * 100, 1) if self.total_sales > 0 else 0.0
