"""
Property routes.

Endpoints
---------
GET  /properties/{property_id}   — retrieve a single property by ID
GET  /properties                 — paginated list of all properties (no filters)
POST /properties/search          — filtered search with full query body

Rules enforced here
-------------------
- Routes call only ``PropertyService`` methods.
- No SQL, no repository logic, no business logic lives in this file.
- All validation is handled by Pydantic v2 schemas.
- HTTP 404 is raised when a property is not found.
- HTTP 422 is raised automatically by FastAPI on validation failure.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator

from app.api.dependencies import get_property_service
from app.domain.property.schemas import PropertySchema
from app.domain.property.service import PropertyService

router = APIRouter(prefix="/properties", tags=["properties"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class PropertyListResponse(BaseModel):
    """Paginated list of properties."""

    items: list[PropertySchema]
    """The properties returned for this page."""

    count: int
    """Number of items in this response (≤ limit)."""

    limit: int
    """The ``limit`` value that was applied."""

    offset: int
    """The ``offset`` value that was applied."""


class PropertySearchRequest(BaseModel):
    """Request body for POST /properties/search.

    All fields are optional.  Providing multiple fields narrows results
    with AND semantics (same as the repository layer).
    """

    city: Optional[str] = Field(
        default=None,
        description="Exact city name (case-sensitive).",
        examples=["London"],
    )
    neighbourhood: Optional[str] = Field(default=None, description="Neighbourhood contains match.")
    intent: Optional[str] = Field(
        default=None,
        description="Listing intent: ``rent`` or ``buy``.",
        examples=["rent"],
    )
    min_price: Optional[int] = Field(default=None, gt=0, description="Lower-bound price filter (inclusive).")
    max_price: Optional[int] = Field(
        default=None,
        gt=0,
        description="Upper-bound price filter (inclusive). Must be > 0.",
        examples=[500_000],
    )
    bedrooms: Optional[int] = Field(
        default=None,
        gt=0,
        description="Exact bedroom count. Must be > 0.",
        examples=[2],
    )
    property_type: Optional[str] = Field(
        default=None,
        description="Property type: ``apartment`` or ``house``.",
        examples=["apartment"],
    )
    radius_km: Optional[float] = Field(
        default=None,
        ge=0,
        description="Max distance from city centre in km (inclusive). Must be ≥ 0.",
        examples=[5.0],
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of results to return (1–100).",
        examples=[20],
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of rows to skip for pagination. Must be ≥ 0.",
        examples=[0],
    )

    @model_validator(mode="after")
    def _validate_intent_enum(self) -> "PropertySearchRequest":
        """Reject intent values other than 'rent' and 'buy'."""
        if self.intent is not None and self.intent not in {"rent", "buy"}:
            raise ValueError("intent must be 'rent' or 'buy'")
        return self

    @model_validator(mode="after")
    def _validate_property_type_enum(self) -> "PropertySearchRequest":
        """Reject property_type values other than 'apartment' and 'house'."""
        if self.property_type is not None and self.property_type not in {"apartment", "house"}:
            raise ValueError("property_type must be 'apartment' or 'house'")
        return self


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

@router.get(
    "/{property_id}",
    response_model=PropertySchema,
    summary="Get a property by ID",
    description="Retrieve a single property record by its integer primary key.",
    responses={
        404: {"description": "Property not found"},
    },
)
async def get_property(
    property_id: int,
    service: Annotated[PropertyService, Depends(get_property_service)],
) -> PropertySchema:
    """Return a single property or raise HTTP 404.

    Args:
        property_id: Integer primary key from the URL path.
        service:     Injected :class:`PropertyService`.

    Returns:
        A :class:`PropertySchema` for the requested property.

    Raises:
        HTTPException: 404 if no property with ``property_id`` exists.
    """
    prop = await service.get_property(property_id)
    if prop is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property with id={property_id} not found.",
        )
    return prop


@router.get(
    "",
    response_model=PropertyListResponse,
    summary="List all properties",
    description=(
        "Return a paginated list of all properties with no filters applied. "
        "Use ``limit`` and ``offset`` query parameters for pagination."
    ),
)
async def list_properties(
    service: Annotated[PropertyService, Depends(get_property_service)],
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Maximum results to return (1–100)."),
    ] = 50,
    offset: Annotated[
        int,
        Query(ge=0, description="Rows to skip for pagination."),
    ] = 0,
) -> PropertyListResponse:
    """Return a paginated list of all properties.

    Args:
        service: Injected :class:`PropertyService`.
        limit:   Maximum rows to return (query param, default 50, max 100).
        offset:  Rows to skip (query param, default 0).

    Returns:
        A :class:`PropertyListResponse` containing the page items and
        pagination metadata.
    """
    items = await service.list_properties(limit=limit, offset=offset)
    return PropertyListResponse(
        items=items,
        count=len(items),
        limit=limit,
        offset=offset,
    )


@router.post(
    "/search",
    response_model=PropertyListResponse,
    summary="Search properties",
    description=(
        "Search properties using optional filters.  All fields in the request "
        "body are optional; multiple fields are combined with AND logic."
    ),
)
async def search_properties(
    body: PropertySearchRequest,
    service: Annotated[PropertyService, Depends(get_property_service)],
) -> PropertyListResponse:
    """Search properties with optional filter criteria.

    Args:
        body:    Validated request body with search parameters.
        service: Injected :class:`PropertyService`.

    Returns:
        A :class:`PropertyListResponse` with matching properties and
        pagination metadata.
    """
    items = await service.search_properties(
        city=body.city,
        neighbourhood=body.neighbourhood,
        intent=body.intent,
        min_price=body.min_price,
        max_price=body.max_price,
        bedrooms=body.bedrooms,
        property_type=body.property_type,
        radius_km=body.radius_km,
        limit=body.limit,
        offset=body.offset,
    )
    return PropertyListResponse(
        items=items,
        count=len(items),
        limit=body.limit,
        offset=body.offset,
    )
