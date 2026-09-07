"""
SQLAlchemy ORM models for the property domain.

Column names and types are derived directly from the source-of-truth CSV
files.  Do NOT add columns that are not present in those files.

Tables
------
- ``properties``   — residential property listings
- ``city_centers`` — geographic centre coordinates per city
"""

from sqlalchemy import Float, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


# ---------------------------------------------------------------------------
# properties
# ---------------------------------------------------------------------------
class Property(Base):
    """ORM model for the ``properties`` table.

    Columns mirror the CSV exactly:
        id, title, city, neighbourhood, intent, price, bedrooms,
        bathrooms, size_sqm, property_type, distance_from_city_km,
        description
    """

    __tablename__ = "properties"

    # Primary key — integer, supplied by the data source (not auto-generated).
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    title: Mapped[str] = mapped_column(String, nullable=False)
    city: Mapped[str] = mapped_column(String, nullable=False)
    neighbourhood: Mapped[str] = mapped_column(String, nullable=False)

    # 'rent' | 'buy'
    intent: Mapped[str] = mapped_column(String, nullable=False)

    # Integer price (no fractional currency in source data)
    price: Mapped[int] = mapped_column(Integer, nullable=False)

    bedrooms: Mapped[int] = mapped_column(Integer, nullable=False)
    bathrooms: Mapped[int] = mapped_column(Integer, nullable=False)
    size_sqm: Mapped[int] = mapped_column(Integer, nullable=False)

    # 'apartment' | 'house'
    property_type: Mapped[str] = mapped_column(String, nullable=False)

    # Pre-computed distance from the city centre; used for radius filtering.
    distance_from_city_km: Mapped[float] = mapped_column(Float, nullable=False)

    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Composite index to accelerate the most common search filter combination.
    __table_args__ = (
        Index("ix_properties_city_intent", "city", "intent"),
        Index("ix_properties_city", "city"),
        Index("ix_properties_intent", "intent"),
        Index("ix_properties_property_type", "property_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<Property id={self.id} city={self.city!r} "
            f"intent={self.intent!r} price={self.price}>"
        )


# ---------------------------------------------------------------------------
# city_centers
# ---------------------------------------------------------------------------
class CityCenter(Base):
    """ORM model for the ``city_centers`` table.

    Columns mirror the CSV exactly:
        city, latitude, longitude

    ``city`` is the primary key — each city name appears exactly once.
    Latitude / longitude are geographic coordinates of the city centre.

    Note: these coordinates are intentionally NOT used for property
    distance calculations in Phase 1.  ``Property.distance_from_city_km``
    is the authoritative proximity field.
    """

    __tablename__ = "city_centers"

    city: Mapped[str] = mapped_column(String, primary_key=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    def __repr__(self) -> str:
        return f"<CityCenter city={self.city!r} lat={self.latitude} lon={self.longitude}>"
