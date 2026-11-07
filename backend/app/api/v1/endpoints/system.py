import platform
import sys

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/")
async def system_info():
    return {
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "python_version": sys.version,
        "platform": platform.system(),
        "architecture": platform.machine(),
        "environment": settings.ENVIRONMENT,
    }
