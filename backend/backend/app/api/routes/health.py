"""
Health check route.

GET /health

Returns a simple liveness signal so load balancers, orchestrators, and
monitoring tools can confirm the API process is running and reachable.
No database query is performed here — a database-aware readiness check
belongs in a separate /readiness endpoint (future phase).
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Response body for GET /health."""

    status: str
    """Always ``"ok"`` while the process is running."""


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness check",
    description=(
        "Returns `{\"status\": \"ok\"}` when the API process is reachable. "
        "Does **not** verify database connectivity."
    ),
)
async def health() -> HealthResponse:
    """Return a liveness signal.

    Returns:
        A :class:`HealthResponse` with ``status="ok"``.
    """
    return HealthResponse(status="ok")
