import logging

from fastapi import APIRouter

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check():
    return {
        "status": "ok",
        "api_configured": settings.is_configured,
        "target_roas": settings.target_roas,
    }
