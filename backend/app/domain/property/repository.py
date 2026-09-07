"""
Property repository — the only layer that contains database query logic.

Rules enforced here:
- Every public method is async.
- Every public method is fully type-hinted.
- Every public method has a docstring.
- No business logic lives here; the repository is purely a data-access
  adapter between the database and the rest of the application.
- ORM objects never escape this module; callers always receive Pydantic
  schema instances.
"""

from typing import Optional

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.property.models import CityCenter, Property
from app.domain.property.schemas import CitySchema, NeighbourhoodSchema, PropertySchema


class PropertyRepository:
    """Async repository for all property-related database operations.

    Args:
        session: An injected :class:`AsyncSession`.  The caller
            (typically the service layer or a DI framework) owns the
            session lifecycle.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Single-record retrieval
    # ------------------------------------------------------------------

    async def get_property(self, property_id: int) -> Optional[PropertySchema]:
        """Retrieve a single property by its primary key.

        Args:
            property_id: The integer primary key of the property.

        Returns:
            A :class:`PropertySchema` if a matching row exists, otherwise
            ``None``.
        """
        stmt = select(Property).where(Property.id == property_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return PropertySchema.model_validate(row)

    # ------------------------------------------------------------------
    # Multi-record retrieval
    # ------------------------------------------------------------------

    async def search_properties(
        self,
        city: Optional[str] = None,
        neighbourhood: Optional[str] = None,
        intent: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        bedrooms: Optional[int] = None,
        property_type: Optional[str] = None,
        radius_km: Optional[float] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PropertySchema]:
        """Search properties using optional filter parameters (AND logic).

        All parameters are optional.  Providing multiple parameters
        narrows results with AND semantics.  Omitting a parameter means
        no filtering on that column.

        Args:
            city:          Exact city name match (case-sensitive).
            intent:        ``'rent'`` or ``'buy'``.
            max_price:     Upper-bound price filter (inclusive: price ≤ max_price).
            bedrooms:      Exact bedroom count match.
            property_type: ``'apartment'`` or ``'house'``.
            radius_km:     Upper-bound distance filter (inclusive:
                           distance_from_city_km ≤ radius_km).
                           Uses the pre-computed column — no geospatial
                           calculation is performed.
            limit:         Maximum rows to return (default 50).
            offset:        Rows to skip for pagination (default 0).

        Returns:
            A (possibly empty) list of :class:`PropertySchema` objects.
        """
        stmt = select(Property)

        if city is not None:
            stmt = stmt.where(Property.city == city)
        if intent is not None:
            stmt = stmt.where(Property.intent == intent)
        if min_price is not None:
            stmt = stmt.where(Property.price >= min_price)
        if max_price is not None:
            stmt = stmt.where(Property.price <= max_price)
        if bedrooms is not None:
            stmt = stmt.where(Property.bedrooms == bedrooms)
        if property_type is not None:
            stmt = stmt.where(Property.property_type == property_type)
        if radius_km is not None:
            stmt = stmt.where(Property.distance_from_city_km <= radius_km)

        stmt = stmt.limit(limit).offset(offset)

        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [PropertySchema.model_validate(row) for row in rows]

    async def list_properties(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PropertySchema]:
        """Return a paginated list of all properties with no filters applied.

        Args:
            limit:  Maximum rows to return (default 50).
            offset: Rows to skip for pagination (default 0).

        Returns:
            A list of :class:`PropertySchema` objects.
        """
        stmt = select(Property).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [PropertySchema.model_validate(row) for row in rows]

    # ------------------------------------------------------------------
    # Lookup / metadata queries
    # ------------------------------------------------------------------

    async def get_cities(self) -> list[CitySchema]:
        """Return all cities with their geographic centre coordinates.

        Data is sourced from the ``city_centers`` table, ordered by city
        name for deterministic output.

        Returns:
            A list of :class:`CitySchema` objects, sorted alphabetically
            by city name.
        """
        stmt = select(CityCenter).order_by(CityCenter.city)
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [CitySchema.model_validate(row) for row in rows]

    async def get_neighbourhoods(self, city: str) -> list[NeighbourhoodSchema]:
        """Return all distinct neighbourhoods for a given city.

        Neighbourhoods are derived from the ``properties`` table, not
        from a standalone lookup table.  Only neighbourhoods that have
        at least one property listing are returned.

        Args:
            city: The city name to filter by (case-sensitive).

        Returns:
            A list of :class:`NeighbourhoodSchema` objects, sorted
            alphabetically by neighbourhood name.  Returns an empty list
            if the city is unknown or has no listings.
        """
        stmt = (
            select(distinct(Property.neighbourhood).label("neighbourhood"))
            .where(Property.city == city)
            .order_by(Property.neighbourhood)
        )
        result = await self._session.execute(stmt)
        # scalars() unpacks the single-column result into plain strings.
        neighbourhood_names: list[str] = list(result.scalars().all())
        return [
            NeighbourhoodSchema(neighbourhood=name, city=city)
            for name in neighbourhood_names
        ]

    async def count_properties(self) -> int:
        """Return the total number of property rows in the database.

        Returns:
            An integer representing the full row count of ``properties``.
        """
        stmt = select(func.count()).select_from(Property)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def count_cities(self) -> int:
        """Return the total number of cities in the database.

        Returns:
            An integer representing the full row count of ``city_centers``.
        """
        stmt = select(func.count()).select_from(CityCenter)
        result = await self._session.execute(stmt)
        return result.scalar_one()
