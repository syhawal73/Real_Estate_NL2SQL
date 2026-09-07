"""
Stats routes.

Endpoints
---------
GET /stats  — Returns overall platform statistics
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_property_service
from app.domain.property.schemas import PlatformStatsResponse
from app.domain.property.service import PropertyService

router = APIRouter(tags=["stats"])

@router.get(
    "/stats",
    response_model=PlatformStatsResponse,
    summary="Get platform statistics",
    description="Returns aggregate statistics for the platform, such as total properties and total cities.",
)
async def get_stats(
    service: Annotated[PropertyService, Depends(get_property_service)],
) -> PlatformStatsResponse:
    """Return overall platform statistics.

    Args:
        service: Injected :class:`PropertyService`.

    Returns:
        A :class:`PlatformStatsResponse` with totals for properties and cities.
    """
    return await service.get_platform_stats()
