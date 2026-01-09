"""Health check endpoints."""

from datetime import datetime
from typing import Dict

from fastapi import APIRouter, Response
from pydantic import BaseModel


router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    version: str
    services: Dict[str, str]


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0",
        services={
            "api": "up",
            "temporal": "unknown",  # Would check actual status
            "storage": "up",
        }
    )


@router.get("/ready")
async def readiness_check() -> Dict[str, str]:
    """Readiness probe for Kubernetes."""
    return {"status": "ready"}


@router.get("/live")
async def liveness_check(response: Response) -> Dict[str, str]:
    """Liveness probe for Kubernetes."""
    return {"status": "alive"}
