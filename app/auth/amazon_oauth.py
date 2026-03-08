import asyncio
import logging
import time
from dataclasses import dataclass, field

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class TokenCache:
    access_token: str = ""
    expires_at: float = 0.0          # unix timestamp
    refresh_buffer_sec: int = 300    # 만료 5분 전 갱신


class AmazonAuthClient:
    """
    Amazon OAuth 2.0 토큰 관리 클라이언트.
    access_token을 자동으로 캐싱하고, 만료 전 자동 갱신한다.
    """

    _instance: "AmazonAuthClient | None" = None
    _lock: asyncio.Lock | None = None

    def __new__(cls) -> "AmazonAuthClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cache = TokenCache()
            cls._instance._lock = asyncio.Lock()
        return cls._instance

    @property
    def _is_token_valid(self) -> bool:
        remaining = self._cache.expires_at - time.time()
        return bool(self._cache.access_token) and remaining > self._cache.refresh_buffer_sec

    async def get_access_token(self) -> str:
        """유효한 access_token 반환. 만료 임박 시 자동 갱신."""
        if self._is_token_valid:
            return self._cache.access_token

        async with self._lock:
            # 락 획득 후 재확인 (다른 코루틴이 이미 갱신했을 수 있음)
            if self._is_token_valid:
                return self._cache.access_token
            await self._refresh_token()

        return self._cache.access_token

    async def _refresh_token(self) -> None:
        """refresh_token으로 새 access_token 발급."""
        logger.info("Refreshing Amazon access token...")

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": settings.amazon_refresh_token,
            "client_id": settings.amazon_client_id,
            "client_secret": settings.amazon_client_secret,
        }

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(settings.amazon_token_url, data=payload)
            response.raise_for_status()
            data = response.json()

        self._cache.access_token = data["access_token"]
        self._cache.expires_at = time.time() + data.get("expires_in", 3600)
        logger.info("Access token refreshed. Expires in %ds", data.get("expires_in", 3600))

    async def get_headers(self) -> dict[str, str]:
        """모든 Amazon API 요청에 필요한 공통 헤더 반환."""
        token = await self.get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Amazon-Advertising-API-ClientId": settings.amazon_client_id,
            "Amazon-Advertising-API-Scope": settings.amazon_profile_id,
            "Content-Type": "application/json",
        }


# 싱글톤 인스턴스
auth_client = AmazonAuthClient()
