"""
Repository tests.

Each test class covers one repository method.  Tests are grouped to
mirror the repository API:

  TestGetProperty          → get_property()
  TestSearchProperties     → search_properties()
  TestListProperties       → list_properties()
  TestGetCities            → get_cities()
  TestGetNeighbourhoods    → get_neighbourhoods()
  TestCountProperties      → count_properties()

All tests use the ``db_session`` fixture from conftest.py, which
provides an isolated, rolled-back transaction per test.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.property.repository import PropertyRepository
from app.domain.property.schemas import CitySchema, NeighbourhoodSchema, PropertySchema

# Seed totals — kept in sync with conftest._PROPERTIES / _CITY_CENTERS
_TOTAL_PROPERTIES = 3
_TOTAL_CITIES = 2


# ===========================================================================
# get_property
# ===========================================================================
class TestGetProperty:

    async def test_returns_schema_when_found(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        result = await repo.get_property(1)

        assert result is not None
        assert isinstance(result, PropertySchema)

    async def test_correct_fields_returned(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        result = await repo.get_property(1)

        assert result is not None
        assert result.id == 1
        assert result.city == "London"
        assert result.neighbourhood == "Wembley"
        assert result.intent == "rent"
        assert result.price == 1_157
        assert result.bedrooms == 2
        assert result.property_type == "apartment"
        assert result.distance_from_city_km == pytest.approx(4.3)

    async def test_returns_none_for_missing_id(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        result = await repo.get_property(99_999)

        assert result is None

    async def test_correct_record_for_id_3(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        result = await repo.get_property(3)

        assert result is not None
        assert result.city == "Paris"
        assert result.intent == "rent"


# ===========================================================================
# search_properties
# ===========================================================================
class TestSearchProperties:

    async def test_no_filters_returns_all(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.search_properties(limit=100)

        assert len(results) == _TOTAL_PROPERTIES
        assert all(isinstance(r, PropertySchema) for r in results)

    # --- individual filters ------------------------------------------------

    async def test_filter_city(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.search_properties(city="London", limit=100)

        assert len(results) == 2
        assert all(r.city == "London" for r in results)

    async def test_filter_unknown_city_returns_empty(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.search_properties(city="UnknownCity")

        assert results == []

    async def test_filter_intent_rent(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.search_properties(intent="rent", limit=100)

        assert len(results) == 2
        assert all(r.intent == "rent" for r in results)

    async def test_filter_intent_buy(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.search_properties(intent="buy", limit=100)

        assert len(results) == 1
        assert results[0].intent == "buy"

    async def test_filter_max_price_inclusive(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        # price=900 and price=1157 should be included; price=450000 excluded
        results = await repo.search_properties(max_price=1_200, limit=100)

        assert all(r.price <= 1_200 for r in results)
        assert len(results) == 2

    async def test_filter_max_price_exact_boundary(self, db_session: AsyncSession) -> None:
        """max_price filter must be inclusive (price ≤ max_price)."""
        repo = PropertyRepository(db_session)
        results = await repo.search_properties(max_price=900, limit=100)

        assert len(results) == 1
        assert results[0].price == 900

    async def test_filter_bedrooms(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.search_properties(bedrooms=2, limit=100)

        assert all(r.bedrooms == 2 for r in results)

    async def test_filter_property_type_apartment(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.search_properties(property_type="apartment", limit=100)

        assert len(results) == 2
        assert all(r.property_type == "apartment" for r in results)

    async def test_filter_property_type_house(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.search_properties(property_type="house", limit=100)

        assert len(results) == 1
        assert results[0].property_type == "house"

    async def test_filter_radius_km_inclusive(self, db_session: AsyncSession) -> None:
        """radius_km filter: distance_from_city_km ≤ radius_km (inclusive)."""
        repo = PropertyRepository(db_session)
        # distances: 3.2, 4.3, 5.1 → only 3.2 and 4.3 pass
        results = await repo.search_properties(radius_km=4.5, limit=100)

        assert all(r.distance_from_city_km <= 4.5 for r in results)
        assert len(results) == 2

    async def test_filter_radius_km_exact_boundary(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        # 3.2 ≤ 3.2 → exactly one property
        results = await repo.search_properties(radius_km=3.2, limit=100)

        assert len(results) == 1
        assert results[0].distance_from_city_km == pytest.approx(3.2)

    # --- combined filters --------------------------------------------------

    async def test_combined_city_and_intent(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.search_properties(city="London", intent="rent", limit=100)

        assert len(results) == 1
        assert results[0].city == "London"
        assert results[0].intent == "rent"

    async def test_combined_city_and_property_type(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.search_properties(city="London", property_type="house", limit=100)

        assert len(results) == 1
        assert results[0].city == "London"
        assert results[0].property_type == "house"

    async def test_combined_filters_no_match(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        # Paris has no 'buy' listings
        results = await repo.search_properties(city="Paris", intent="buy", limit=100)

        assert results == []

    # --- pagination --------------------------------------------------------

    async def test_limit_restricts_results(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.search_properties(limit=2)

        assert len(results) == 2

    async def test_offset_skips_rows(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        all_results = await repo.search_properties(limit=100)
        offset_results = await repo.search_properties(limit=100, offset=1)

        assert len(offset_results) == len(all_results) - 1

    async def test_offset_beyond_total_returns_empty(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.search_properties(limit=50, offset=1_000)

        assert results == []


# ===========================================================================
# list_properties
# ===========================================================================
class TestListProperties:

    async def test_returns_all_rows(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.list_properties(limit=100)

        assert len(results) == _TOTAL_PROPERTIES
        assert all(isinstance(r, PropertySchema) for r in results)

    async def test_respects_limit(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.list_properties(limit=1)

        assert len(results) == 1

    async def test_respects_offset(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.list_properties(limit=100, offset=2)

        assert len(results) == _TOTAL_PROPERTIES - 2

    async def test_default_limit_is_50(self, db_session: AsyncSession) -> None:
        """Default limit=50 should not truncate a dataset smaller than 50."""
        repo = PropertyRepository(db_session)
        results = await repo.list_properties()

        assert len(results) == _TOTAL_PROPERTIES

    async def test_offset_beyond_total_returns_empty(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.list_properties(limit=50, offset=1_000)

        assert results == []


# ===========================================================================
# get_cities
# ===========================================================================
class TestGetCities:

    async def test_returns_city_schema_instances(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.get_cities()

        assert all(isinstance(r, CitySchema) for r in results)

    async def test_correct_count(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.get_cities()

        assert len(results) == _TOTAL_CITIES

    async def test_london_coordinates(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.get_cities()
        london = next(r for r in results if r.city == "London")

        assert london.latitude == pytest.approx(51.5074)
        assert london.longitude == pytest.approx(-0.1278)

    async def test_paris_coordinates(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.get_cities()
        paris = next(r for r in results if r.city == "Paris")

        assert paris.latitude == pytest.approx(48.8566)
        assert paris.longitude == pytest.approx(2.3522)

    async def test_results_are_alphabetically_ordered(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.get_cities()
        names = [r.city for r in results]

        assert names == sorted(names)


# ===========================================================================
# get_neighbourhoods
# ===========================================================================
class TestGetNeighbourhoods:

    async def test_returns_neighbourhood_schema_instances(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.get_neighbourhoods("London")

        assert all(isinstance(r, NeighbourhoodSchema) for r in results)

    async def test_london_neighbourhoods(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.get_neighbourhoods("London")
        names = {r.neighbourhood for r in results}

        assert names == {"Wembley", "Canary Wharf"}

    async def test_paris_neighbourhoods(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.get_neighbourhoods("Paris")
        names = {r.neighbourhood for r in results}

        assert names == {"Montmartre"}

    async def test_city_field_set_correctly(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.get_neighbourhoods("London")

        assert all(r.city == "London" for r in results)

    async def test_unknown_city_returns_empty_list(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.get_neighbourhoods("UnknownCity")

        assert results == []

    async def test_results_are_alphabetically_ordered(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        results = await repo.get_neighbourhoods("London")
        names = [r.neighbourhood for r in results]

        assert names == sorted(names)

    async def test_no_duplicate_neighbourhoods(self, db_session: AsyncSession) -> None:
        """Each neighbourhood name must appear at most once."""
        repo = PropertyRepository(db_session)
        results = await repo.get_neighbourhoods("London")
        names = [r.neighbourhood for r in results]

        assert len(names) == len(set(names))


# ===========================================================================
# count_properties
# ===========================================================================
class TestCountProperties:

    async def test_returns_total_seeded_count(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        count = await repo.count_properties()

        assert count == _TOTAL_PROPERTIES

    async def test_return_type_is_int(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        count = await repo.count_properties()

        assert isinstance(count, int)

    async def test_count_is_non_negative(self, db_session: AsyncSession) -> None:
        repo = PropertyRepository(db_session)
        count = await repo.count_properties()

        assert count >= 0
