import asyncio
import logging

import httpx

from app.auth.amazon_oauth import auth_client
from app.config import settings

logger = logging.getLogger(__name__)

_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


async def _request_with_retry(
    method: str,
    url: str,
    max_retries: int = 3,
    **kwargs,
) -> httpx.Response:
    """
    Amazon API 공통 요청 래퍼.
    - 인증 헤더 자동 주입
    - 429 / 5xx 에 exponential backoff 재시도
    """
    headers = await auth_client.get_headers()
    # 호출자가 추가 헤더를 넘기면 병합
    headers.update(kwargs.pop("headers", {}))

    last_exc: Exception = RuntimeError("No attempts made")

    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(max_retries):
            try:
                logger.debug("%s %s (attempt %d)", method.upper(), url, attempt + 1)
                response = await client.request(method, url, headers=headers, **kwargs)

                if response.status_code not in _RETRY_STATUS_CODES:
                    response.raise_for_status()
                    return response

                # 재시도 대상 상태코드
                wait = 2 ** attempt
                logger.warning(
                    "HTTP %d from %s — retrying in %ds...",
                    response.status_code, url, wait,
                )
                await asyncio.sleep(wait)
                last_exc = httpx.HTTPStatusError(
                    f"HTTP {response.status_code}",
                    request=response.request,
                    response=response,
                )

            except httpx.TimeoutException as e:
                wait = 2 ** attempt
                logger.warning("Timeout on %s — retrying in %ds...", url, wait)
                await asyncio.sleep(wait)
                last_exc = e

    raise last_exc


async def api_get(url: str, **kwargs) -> httpx.Response:
    return await _request_with_retry("GET", url, **kwargs)


async def api_post(url: str, **kwargs) -> httpx.Response:
    return await _request_with_retry("POST", url, **kwargs)


async def api_put(url: str, **kwargs) -> httpx.Response:
    return await _request_with_retry("PUT", url, **kwargs)


def build_url(path: str) -> str:
    return f"{settings.amazon_api_base}{path}"
