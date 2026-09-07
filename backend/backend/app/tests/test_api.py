"""
API integration tests — Phase 2.

Each test class maps to one endpoint group:

  TestHealthEndpoint                → GET /health
  TestGetPropertyEndpoint           → GET /properties/{property_id}
  TestListPropertiesEndpoint        → GET /properties
  TestSearchPropertiesEndpoint      → POST /properties/search
  TestGetCitiesEndpoint             → GET /metadata/cities
  TestGetNeighbourhoodsEndpoint     → GET /metadata/cities/{city}/neighbourhoods

Strategy
--------
- ``AsyncClient`` from ``httpx`` drives the FastAPI app via ASGI (no real
  network calls).
- The ``api_client`` fixture reuses the Phase 1 ``db_session`` fixture so
  every test runs inside a rolled-back transaction — identical isolation
  to the repository tests.
- The FastAPI ``get_db`` dependency is overridden to inject the test
  session instead of opening a new one.

Prerequisites
-------------
Set ``TEST_DATABASE_URL`` in your environment or ``.env``.  The seed data
from ``conftest.py`` is used by all tests.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_db
from app.main import app

# ---------------------------------------------------------------------------
# Seed constants (kept in sync with conftest.py)
# ---------------------------------------------------------------------------
_TOTAL_SEEDED_PROPERTIES = 3
_TOTAL_SEEDED_CITIES = 2


# ---------------------------------------------------------------------------
# Fixture: API client wired to the isolated test session
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def api_client(db_session: AsyncSession):
    """Yield an AsyncClient whose DB calls run inside the test transaction.

    The ``get_db`` dependency is overridden so that every request uses
    the same ``db_session`` the test has — ensuring the seeded rows are
    visible and all changes are rolled back after the test.
    """

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client

    app.dependency_overrides.clear()


# ===========================================================================
# GET /health
# ===========================================================================

class TestHealthEndpoint:

    async def test_returns_200(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/health")
        assert response.status_code == 200

    async def test_body_has_status_ok(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/health")
        assert response.json() == {"status": "ok"}

    async def test_content_type_is_json(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/health")
        assert "application/json" in response.headers["content-type"]


# ===========================================================================
# GET /properties/{property_id}
# ===========================================================================

class TestGetPropertyEndpoint:

    async def test_returns_200_for_existing_id(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/properties/1")
        assert response.status_code == 200

    async def test_correct_fields_returned(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/properties/1")
        data = response.json()

        assert data["id"] == 1
        assert data["city"] == "London"
        assert data["neighbourhood"] == "Wembley"
        assert data["intent"] == "rent"
        assert data["price"] == 1_157
        assert data["bedrooms"] == 2
        assert data["property_type"] == "apartment"
        assert pytest.approx(data["distance_from_city_km"], abs=1e-4) == 4.3

    async def test_all_schema_fields_present(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/properties/1")
        data = response.json()
        expected_fields = {
            "id", "title", "city", "neighbourhood", "intent",
            "price", "bedrooms", "bathrooms", "size_sqm",
            "property_type", "distance_from_city_km", "description",
        }
        assert expected_fields.issubset(data.keys())

    async def test_returns_404_for_missing_id(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/properties/99999")
        assert response.status_code == 404

    async def test_404_body_contains_detail(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/properties/99999")
        assert "detail" in response.json()

    async def test_paris_property_returned_correctly(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/properties/3")
        data = response.json()
        assert data["city"] == "Paris"
        assert data["intent"] == "rent"


# ===========================================================================
# GET /properties
# ===========================================================================

class TestListPropertiesEndpoint:

    async def test_returns_200(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/properties")
        assert response.status_code == 200

    async def test_returns_all_seeded_properties(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/properties")
        data = response.json()
        assert data["count"] == _TOTAL_SEEDED_PROPERTIES
        assert len(data["items"]) == _TOTAL_SEEDED_PROPERTIES

    async def test_response_has_pagination_metadata(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/properties")
        data = response.json()
        assert "items" in data
        assert "count" in data
        assert "limit" in data
        assert "offset" in data

    async def test_default_limit_in_response(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/properties")
        assert response.json()["limit"] == 50

    async def test_custom_limit_respected(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/properties?limit=1")
        data = response.json()
        assert len(data["items"]) == 1
        assert data["limit"] == 1

    async def test_offset_skips_rows(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/properties?offset=2")
        data = response.json()
        assert data["count"] == _TOTAL_SEEDED_PROPERTIES - 2

    async def test_limit_above_100_returns_422(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/properties?limit=101")
        assert response.status_code == 422

    async def test_negative_offset_returns_422(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/properties?offset=-1")
        assert response.status_code == 422

    async def test_limit_zero_returns_422(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/properties?limit=0")
        assert response.status_code == 422


# ===========================================================================
# POST /properties/search
# ===========================================================================

class TestSearchPropertiesEndpoint:

    async def test_empty_body_returns_all(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/properties/search", json={})
        data = response.json()
        assert response.status_code == 200
        assert data["count"] == _TOTAL_SEEDED_PROPERTIES

    async def test_filter_by_city(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/properties/search", json={"city": "London"})
        data = response.json()
        assert response.status_code == 200
        assert data["count"] == 2
        assert all(item["city"] == "London" for item in data["items"])

    async def test_filter_by_intent_rent(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/properties/search", json={"intent": "rent"})
        data = response.json()
        assert data["count"] == 2
        assert all(item["intent"] == "rent" for item in data["items"])

    async def test_filter_by_intent_buy(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/properties/search", json={"intent": "buy"})
        data = response.json()
        assert data["count"] == 1
        assert data["items"][0]["intent"] == "buy"

    async def test_filter_by_max_price(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/properties/search", json={"max_price": 1_200})
        data = response.json()
        assert all(item["price"] <= 1_200 for item in data["items"])
        assert data["count"] == 2

    async def test_filter_by_bedrooms(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/properties/search", json={"bedrooms": 2})
        data = response.json()
        assert all(item["bedrooms"] == 2 for item in data["items"])

    async def test_filter_by_property_type_apartment(self, api_client: AsyncClient) -> None:
        response = await api_client.post(
            "/properties/search", json={"property_type": "apartment"}
        )
        data = response.json()
        assert data["count"] == 2
        assert all(item["property_type"] == "apartment" for item in data["items"])

    async def test_filter_by_radius_km(self, api_client: AsyncClient) -> None:
        # distances: 3.2, 4.3, 5.1 → only 3.2 and 4.3 are ≤ 4.5
        response = await api_client.post("/properties/search", json={"radius_km": 4.5})
        data = response.json()
        assert data["count"] == 2
        assert all(item["distance_from_city_km"] <= 4.5 for item in data["items"])

    async def test_combined_city_and_intent(self, api_client: AsyncClient) -> None:
        response = await api_client.post(
            "/properties/search", json={"city": "London", "intent": "rent"}
        )
        data = response.json()
        assert data["count"] == 1
        assert data["items"][0]["city"] == "London"
        assert data["items"][0]["intent"] == "rent"

    async def test_no_match_returns_empty(self, api_client: AsyncClient) -> None:
        response = await api_client.post(
            "/properties/search", json={"city": "Paris", "intent": "buy"}
        )
        data = response.json()
        assert data["count"] == 0
        assert data["items"] == []

    async def test_limit_in_body_respected(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/properties/search", json={"limit": 1})
        data = response.json()
        assert len(data["items"]) == 1
        assert data["limit"] == 1

    async def test_offset_in_body_respected(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/properties/search", json={"offset": 2})
        data = response.json()
        assert data["count"] == _TOTAL_SEEDED_PROPERTIES - 2

    # --- validation ---------------------------------------------------------

    async def test_max_price_zero_returns_422(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/properties/search", json={"max_price": 0})
        assert response.status_code == 422

    async def test_max_price_negative_returns_422(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/properties/search", json={"max_price": -1})
        assert response.status_code == 422

    async def test_bedrooms_zero_returns_422(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/properties/search", json={"bedrooms": 0})
        assert response.status_code == 422

    async def test_radius_km_negative_returns_422(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/properties/search", json={"radius_km": -1.0})
        assert response.status_code == 422

    async def test_radius_km_zero_is_valid(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/properties/search", json={"radius_km": 0.0})
        assert response.status_code == 200

    async def test_limit_above_100_returns_422(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/properties/search", json={"limit": 101})
        assert response.status_code == 422

    async def test_offset_negative_returns_422(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/properties/search", json={"offset": -1})
        assert response.status_code == 422

    async def test_invalid_intent_returns_422(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/properties/search", json={"intent": "lease"})
        assert response.status_code == 422

    async def test_invalid_property_type_returns_422(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/properties/search", json={"property_type": "villa"})
        assert response.status_code == 422

    async def test_response_has_pagination_metadata(self, api_client: AsyncClient) -> None:
        response = await api_client.post("/properties/search", json={})
        data = response.json()
        assert "items" in data
        assert "count" in data
        assert "limit" in data
        assert "offset" in data


# ===========================================================================
# GET /metadata/cities
# ===========================================================================

class TestGetCitiesEndpoint:

    async def test_returns_200(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/metadata/cities")
        assert response.status_code == 200

    async def test_returns_all_seeded_cities(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/metadata/cities")
        data = response.json()
        assert len(data) == _TOTAL_SEEDED_CITIES

    async def test_city_schema_fields_present(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/metadata/cities")
        for city in response.json():
            assert "city" in city
            assert "latitude" in city
            assert "longitude" in city

    async def test_london_coordinates(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/metadata/cities")
        london = next(c for c in response.json() if c["city"] == "London")
        assert pytest.approx(london["latitude"], abs=1e-4) == 51.5074
        assert pytest.approx(london["longitude"], abs=1e-4) == -0.1278

    async def test_results_are_alphabetically_ordered(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/metadata/cities")
        names = [c["city"] for c in response.json()]
        assert names == sorted(names)


# ===========================================================================
# GET /metadata/cities/{city}/neighbourhoods
# ===========================================================================

class TestGetNeighbourhoodsEndpoint:

    async def test_returns_200_for_known_city(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/metadata/cities/London/neighbourhoods")
        assert response.status_code == 200

    async def test_london_neighbourhoods(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/metadata/cities/London/neighbourhoods")
        names = {item["neighbourhood"] for item in response.json()}
        assert names == {"Wembley", "Canary Wharf"}

    async def test_paris_neighbourhoods(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/metadata/cities/Paris/neighbourhoods")
        names = {item["neighbourhood"] for item in response.json()}
        assert names == {"Montmartre"}

    async def test_neighbourhood_schema_fields_present(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/metadata/cities/London/neighbourhoods")
        for item in response.json():
            assert "neighbourhood" in item
            assert "city" in item

    async def test_city_field_matches_path(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/metadata/cities/London/neighbourhoods")
        assert all(item["city"] == "London" for item in response.json())

    async def test_unknown_city_returns_empty_list(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/metadata/cities/UnknownCity/neighbourhoods")
        assert response.status_code == 200
        assert response.json() == []

    async def test_results_are_alphabetically_ordered(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/metadata/cities/London/neighbourhoods")
        names = [item["neighbourhood"] for item in response.json()]
        assert names == sorted(names)

    async def test_no_duplicate_neighbourhoods(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/metadata/cities/London/neighbourhoods")
        names = [item["neighbourhood"] for item in response.json()]
        assert len(names) == len(set(names))
