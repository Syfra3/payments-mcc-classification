"""Health check API router."""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from app.core.database import get_db_session
from app.core.dependencies import get_llm_provider
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check() -> dict:
    """
    Liveness probe - checks if service is running.

    Returns:
    - 200: Service is alive
    """
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/ready")
async def readiness_check(
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Readiness probe - checks if service is ready to handle requests.

    Checks:
    - Database connectivity
    - LLM provider availability

    Returns:
    - 200: Service is ready
    - 503: Service is not ready
    """
    readiness_data = {
        "status": "ready",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "database": "unknown",
            "llm": "unknown",
        },
    }

    # Check database
    try:
        result = await session.execute(text("SELECT 1"))
        readiness_data["checks"]["database"] = "ok"
    except Exception as e:
        readiness_data["checks"]["database"] = f"failed: {str(e)}"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database check failed",
        )

    # Check LLM provider
    try:
        llm = get_llm_provider()
        # Simple check - verify provider is configured
        if llm:
            readiness_data["checks"]["llm"] = "ok"
        else:
            readiness_data["checks"]["llm"] = "not_configured"
    except Exception as e:
        readiness_data["checks"]["llm"] = f"failed: {str(e)}"
        # LLM is optional, don't fail readiness for it
        readiness_data["checks"]["llm"] = "unavailable"

    return readiness_data
