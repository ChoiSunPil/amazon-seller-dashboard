import asyncio
import csv
import gzip
import io
import logging
from datetime import date, timedelta

import httpx

from app.api.base import api_get, api_post, build_url
from app.models.schemas import (
    KeywordMetrics,
    ReportResponse,
    ReportStatus,
    ReportType,
)

logger = logging.getLogger(__name__)

POLL_INTERVAL_SEC = 30
POLL_TIMEOUT_SEC  = 600  # 최대 10분 대기


# ─────────────────────────────────────────────────────────────
# 리포트 요청
# ─────────────────────────────────────────────────────────────

async def request_report(
    report_type: ReportType,
    report_date: date,
) -> str:
    """
    Amazon에 리포트 생성 요청.
    Returns: reportId
    """
    metrics = _get_metrics(report_type)

    payload = {
        "name":         f"{report_type.value}_{report_date.isoformat()}",
        "startDate":    report_date.isoformat(),
        "endDate":      report_date.isoformat(),
        "configuration": {
            "adProduct":         "SPONSORED_PRODUCTS",
            "groupBy":           ["searchTerm"] if report_type == ReportType.SEARCH_TERM else ["targeting"],
            "columns":           metrics,
            "reportTypeId":      report_type.value,
            "timeUnit":          "SUMMARY",
            "format":            "GZIP_JSON",
        },
    }

    response = await api_post(build_url("/reporting/reports"), json=payload)
    data = response.json()
    report_id = data["reportId"]
    logger.info("Report requested: id=%s type=%s date=%s", report_id, report_type.value, report_date)
    return report_id


def _get_metrics(report_type: ReportType) -> list[str]:
    """리포트 타입별 요청할 컬럼 목록"""
    common = [
        "campaignName", "adGroupName", "impressions", "clicks",
        "cost", "purchases7d", "sales7d", "costPerClick",
        "clickThroughRate", "purchasesPromotedUnits7d",
    ]
    if report_type == ReportType.SEARCH_TERM:
        return common + ["searchTerm", "targeting", "matchType"]
    return common + ["targeting", "matchType", "topOfSearchImpressionShare"]


# ─────────────────────────────────────────────────────────────
# 폴링
# ─────────────────────────────────────────────────────────────

async def poll_until_complete(report_id: str) -> ReportResponse:
    """
    reportId로 완료될 때까지 폴링.
    POLL_TIMEOUT_SEC 초과 시 TimeoutError 발생.
    """
    url = build_url(f"/reporting/reports/{report_id}")
    elapsed = 0

    while elapsed < POLL_TIMEOUT_SEC:
        response = await api_get(url)
        report   = ReportResponse.model_validate(response.json())

        logger.debug("Report %s status: %s", report_id, report.status)

        if report.status == ReportStatus.COMPLETED:
            return report

        if report.status == ReportStatus.FAILED:
            raise RuntimeError(f"Report {report_id} failed on Amazon side")

        await asyncio.sleep(POLL_INTERVAL_SEC)
        elapsed += POLL_INTERVAL_SEC

    raise TimeoutError(f"Report {report_id} not completed within {POLL_TIMEOUT_SEC}s")


# ─────────────────────────────────────────────────────────────
# 다운로드 & 파싱
# ─────────────────────────────────────────────────────────────

async def download_report(download_url: str) -> list[dict]:
    """
    downloadUrl에서 gzip JSON 다운로드 후 파싱.
    Returns: raw dict 리스트
    """
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(download_url)
        response.raise_for_status()

    content = response.content

    # gzip 압축 해제
    try:
        content = gzip.decompress(content)
    except OSError:
        pass  # 이미 압축 해제된 경우

    import json
    records = json.loads(content.decode("utf-8"))
    logger.info("Downloaded %d rows from report", len(records))
    return records


def parse_search_term_records(records: list[dict]) -> list[KeywordMetrics]:
    """
    Amazon API JSON 레코드 → KeywordMetrics 리스트 변환.
    컬럼명은 Amazon Advertising API v3 기준.
    """
    result: list[KeywordMetrics] = []

    for row in records:
        try:
            km = KeywordMetrics(
                campaign_name = row.get("campaignName", ""),
                ad_group_name = row.get("adGroupName", ""),
                search_term   = row.get("searchTerm", row.get("targeting", "")),
                targeting     = row.get("targeting", ""),
                match_type    = row.get("matchType", ""),
                impressions   = int(row.get("impressions", 0)),
                clicks        = int(row.get("clicks", 0)),
                spend         = float(row.get("cost", 0)),
                sales         = float(row.get("sales7d", 0)),
                orders        = int(row.get("purchases7d", 0)),
                units         = int(row.get("purchasesPromotedUnits7d", 0)),
                cpc           = float(row.get("costPerClick", 0)),
            )
            result.append(km)
        except Exception as e:
            logger.warning("Skipping malformed row: %s | error: %s", row, e)

    logger.info("Parsed %d keyword metrics", len(result))
    return result


# ─────────────────────────────────────────────────────────────
# 고수준 인터페이스 (한 번에 호출)
# ─────────────────────────────────────────────────────────────

async def fetch_search_term_report(
    target_date: date | None = None,
) -> list[KeywordMetrics]:
    """
    Search Term 리포트 전체 파이프라인.
    target_date 미지정 시 전일(yesterday) 기준.

    Returns: KeywordMetrics 리스트
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    logger.info("Fetching search term report for %s", target_date)

    report_id    = await request_report(ReportType.SEARCH_TERM, target_date)
    report       = await poll_until_complete(report_id)
    records      = await download_report(report.download_url)
    metrics      = parse_search_term_records(records)

    return metrics


async def fetch_targeting_report(
    target_date: date | None = None,
) -> list[KeywordMetrics]:
    """Targeting 리포트 전체 파이프라인."""
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    logger.info("Fetching targeting report for %s", target_date)

    report_id = await request_report(ReportType.TARGETING, target_date)
    report    = await poll_until_complete(report_id)
    records   = await download_report(report.download_url)
    metrics   = parse_search_term_records(records)

    return metrics
