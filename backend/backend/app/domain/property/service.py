"""
Property service layer.

The service is the public API of the property domain.  In Phase 1 it is
a thin pass-through to :class:`PropertyRepository`.  Business logic,
enrichment, and orchestration will be added in later phases without
touching the repository.

Design decisions:
- The service owns a ``PropertyRepository`` instance; the repository
  does not know the service exists.
- The session is injected into the service, which forwards it to the
  repository. This keeps the DI graph flat and testable.
- Return types mirror the repository exactly — Pydantic schemas only.
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.property.repository import PropertyRepository
from app.domain.property.schemas import CitySchema, NeighbourhoodSchema, PropertySchema, PlatformStatsResponse


class PropertyService:
    """Service layer for all property-related use cases.

    Args:
        session: An injected :class:`AsyncSession`.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._repo = PropertyRepository(session)

    # ------------------------------------------------------------------
    # Single-record
    # ------------------------------------------------------------------

    async def get_property(self, property_id: int) -> Optional[PropertySchema]:
        """Retrieve a single property by ID.

        Args:
            property_id: The integer primary key of the property.

        Returns:
            A :class:`PropertySchema` if found, otherwise ``None``.
        """
        return await self._repo.get_property(property_id)

    # ------------------------------------------------------------------
    # Multi-record
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
        """Search properties with optional filters.

        See :meth:`PropertyRepository.search_properties` for full
        parameter documentation.
        """
        return await self._repo.search_properties(
            city=city,
            neighbourhood=neighbourhood,
            intent=intent,
            min_price=min_price,
            max_price=max_price,
            bedrooms=bedrooms,
            property_type=property_type,
            radius_km=radius_km,
            limit=limit,
            offset=offset,
        )

    async def list_properties(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PropertySchema]:
        """Return a paginated list of all properties with no filters.

        Args:
            limit:  Maximum rows to return (default 50).
            offset: Rows to skip for pagination (default 0).

        Returns:
            A list of :class:`PropertySchema` objects.
        """
        return await self._repo.list_properties(limit=limit, offset=offset)

    # ------------------------------------------------------------------
    # Lookup / metadata
    # ------------------------------------------------------------------

    async def get_cities(self) -> list[CitySchema]:
        """Return all cities with geographic centre coordinates.

        Returns:
            A list of :class:`CitySchema` objects sorted by city name.
        """
        return await self._repo.get_cities()

    async def get_neighbourhoods(self, city: str) -> list[NeighbourhoodSchema]:
        """Return all distinct neighbourhoods for a given city.

        Args:
            city: The city name to look up (case-sensitive).

        Returns:
            A list of :class:`NeighbourhoodSchema` objects sorted
            alphabetically.  Returns an empty list for unknown cities.
        """
        return await self._repo.get_neighbourhoods(city)

    async def count_properties(self) -> int:
        """Return the total property count.

        Returns:
            Total number of rows in the ``properties`` table.
        """
        return await self._repo.count_properties()

    async def get_platform_stats(self) -> PlatformStatsResponse:
        """Return overall platform statistics.

        Returns:
            A :class:`PlatformStatsResponse` with totals for properties and cities.
        """
        total_properties = await self._repo.count_properties()
        total_cities = await self._repo.count_cities()
        return PlatformStatsResponse(
            total_properties=total_properties,
            total_cities=total_cities,
        )
