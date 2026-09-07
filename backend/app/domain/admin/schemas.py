from datetime import datetime
from pydantic import BaseModel, Field


class OwnershipIn(BaseModel):
    owner_type: str = Field(pattern="^(agent|user|agency)$")
    owner_id: str | None = None
    owner_name: str = Field(min_length=1, max_length=255)
    owner_email: str | None = None


class PropertyCreateRequest(BaseModel):
    title: str
    city: str
    neighbourhood: str
    intent: str = Field(pattern="^(rent|buy)$")
    price: int = Field(gt=0)
    bedrooms: int = Field(gt=0)
    bathrooms: int = Field(gt=0)
    size_sqm: int = Field(gt=0)
    property_type: str = Field(pattern="^(apartment|house)$")
    distance_from_city_km: float = Field(ge=0)
    description: str
    id: int | None = Field(default=None, gt=0)
    ownership: OwnershipIn | None = None


class PropertyUpdateRequest(BaseModel):
    title: str | None = None
    city: str | None = None
    neighbourhood: str | None = None
    intent: str | None = Field(default=None, pattern="^(rent|buy)$")
    price: int | None = Field(default=None, gt=0)
    bedrooms: int | None = Field(default=None, gt=0)
    bathrooms: int | None = Field(default=None, gt=0)
    size_sqm: int | None = Field(default=None, gt=0)
    property_type: str | None = Field(default=None, pattern="^(apartment|house)$")
    distance_from_city_km: float | None = Field(default=None, ge=0)
    description: str | None = None
    ownership: OwnershipIn | None = None


class OwnershipResponse(OwnershipIn):
    property_id: int
    updated_at: datetime


class AdminStatsResponse(BaseModel):
    total_properties: int
    total_users: int
    total_conversations: int
    total_messages: int
    total_favorites: int
    recent_zero_result_searches: int


class AuditLogResponse(BaseModel):
    id: str
    admin_user_id: str | None
    action: str
    resource_type: str
    resource_id: str | None
    details: dict
    created_at: datetime
