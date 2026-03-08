import logging

from fastapi import FastAPI

from app.config import settings
from app.routers import health

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Amazon SP ROAS 최적화 대시보드",
    description="Sponsored Products 광고 ROAS 자동 최적화",
    version="0.1.0",
)

app.include_router(health.router)


@app.get("/")
async def root():
    return {
        "service": "amazon-seller-dashboard",
        "target_roas": settings.target_roas,
        "api_configured": settings.is_configured,
        "docs": "/docs",
    }
