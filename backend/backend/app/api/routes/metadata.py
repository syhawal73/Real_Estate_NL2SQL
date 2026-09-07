"""
Metadata routes.

Endpoints
---------
GET /metadata/cities                          — list all cities with coordinates
GET /metadata/cities/{city}/neighbourhoods    — list neighbourhoods for a city

These endpoints expose lookup / reference data that callers use to
populate filter dropdowns or validate user input before calling the
search endpoint.  No business logic lives here; everything delegates
to :class:`PropertyService`.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_property_service
from app.domain.property.schemas import CitySchema, NeighbourhoodSchema
from app.domain.property.service import PropertyService

router = APIRouter(prefix="/metadata", tags=["metadata"])


# ---------------------------------------------------------------------------
# Response schemas are re-exported directly from the domain layer.
# No new wrappers needed — CitySchema and NeighbourhoodSchema are complete.
# ---------------------------------------------------------------------------


@router.get(
    "/cities",
    response_model=list[CitySchema],
    summary="List all cities",
    description=(
        "Return every city that has at least one property listing, along with "
        "its geographic centre coordinates. Results are sorted alphabetically."
    ),
)
async def get_cities(
    service: Annotated[PropertyService, Depends(get_property_service)],
) -> list[CitySchema]:
    """Return all cities with geographic centre coordinates.

    Args:
        service: Injected :class:`PropertyService`.

    Returns:
        A list of :class:`CitySchema` objects sorted alphabetically by
        city name.
    """
    return await service.get_cities()


@router.get(
    "/cities/{city}/neighbourhoods",
    response_model=list[NeighbourhoodSchema],
    summary="List neighbourhoods for a city",
    description=(
        "Return all distinct neighbourhoods that have at least one property "
        "listing in the given city. Results are sorted alphabetically. "
        "Returns an empty list for unknown cities (not a 404)."
    ),
)
async def get_neighbourhoods(
    city: str,
    service: Annotated[PropertyService, Depends(get_property_service)],
) -> list[NeighbourhoodSchema]:
    """Return all distinct neighbourhoods for a given city.

    Args:
        city:    City name from the URL path (case-sensitive).
        service: Injected :class:`PropertyService`.

    Returns:
        A list of :class:`NeighbourhoodSchema` objects sorted
        alphabetically.  Empty list if city is unknown.
    """
    return await service.get_neighbourhoods(city)
