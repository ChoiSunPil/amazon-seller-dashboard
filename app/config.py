from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Amazon Advertising API
    amazon_client_id: str = ""
    amazon_client_secret: str = ""
    amazon_refresh_token: str = ""
    amazon_profile_id: str = ""
    amazon_marketplace_id: str = "ATVPDKIKX0DER"  # US 기본값

    # 최적화 설정
    target_roas: float = 5.0
    target_acos: float = 0.20
    max_bid_change_pct: float = 0.30
    min_clicks_for_bid: int = 5
    min_bid: float = 0.05
    min_spend_negative: float = 5.0

    # 서버
    api_port: int = 8000
    log_level: str = "INFO"

    # DB
    database_url: str = "sqlite+aiosqlite:///./dashboard.db"

    @property
    def amazon_api_base(self) -> str:
        return "https://advertising-api.amazon.com"

    @property
    def amazon_token_url(self) -> str:
        return "https://api.amazon.com/auth/o2/token"

    @property
    def is_configured(self) -> bool:
        """API 키가 설정됐는지 확인"""
        return all([
            self.amazon_client_id,
            self.amazon_client_secret,
            self.amazon_refresh_token,
            self.amazon_profile_id,
        ])


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
