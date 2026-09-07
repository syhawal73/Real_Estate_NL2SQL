"""
Pydantic v2 schemas for the property domain.

These are the data-transfer objects that cross layer boundaries.  The
repository converts ORM rows into these schemas; the service and
(future) API layer work exclusively with schemas — never raw ORM objects.

Schemas
-------
- PropertySchema       — full property record
- CitySchema           — city name + geographic centre coordinates
- NeighbourhoodSchema  — distinct neighbourhood name scoped to a city
"""

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Property
# ---------------------------------------------------------------------------
class PropertySchema(BaseModel):
    """Full representation of a single property record.

    Field types mirror the ORM model exactly.
    ``from_attributes=True`` enables construction from SQLAlchemy ORM
    instances via ``PropertySchema.model_validate(orm_obj)``.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    city: str
    neighbourhood: str
    intent: str              # 'rent' | 'buy'
    price: int
    bedrooms: int
    bathrooms: int
    size_sqm: int
    property_type: str       # 'apartment' | 'house'
    distance_from_city_km: float
    description: str


# ---------------------------------------------------------------------------
# City
# ---------------------------------------------------------------------------
class CitySchema(BaseModel):
    """City with its geographic centre coordinates.

    Maps directly to a ``city_centers`` row.
    ``from_attributes=True`` allows construction from a CityCenter ORM
    instance via ``CitySchema.model_validate(orm_obj)``.
    """

    model_config = ConfigDict(from_attributes=True)

    city: str
    latitude: float
    longitude: float


# ---------------------------------------------------------------------------
# Neighbourhood
# ---------------------------------------------------------------------------
class NeighbourhoodSchema(BaseModel):
    """A distinct neighbourhood name scoped to a city.

    Neighbourhoods are not a standalone table — they are derived from the
    distinct values in ``properties.neighbourhood`` for a given city.
    The ``city`` field is included so callers always have full context.
    """

    model_config = ConfigDict(from_attributes=True)

    neighbourhood: str
    city: str


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------
class PlatformStatsResponse(BaseModel):
    """Overall platform statistics.
    
    Contains totals derived from the database.
    """
    total_properties: int
    total_cities: int
