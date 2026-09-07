from __future__ import annotations

from sqlalchemy import func, select, update
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_admin
from app.domain.admin.models import AdminAuditLog, AdminSetting, PropertyOwnership, PropertyFlags
from app.domain.admin.schemas import AdminStatsResponse, AuditLogResponse, OwnershipResponse, PropertyCreateRequest, PropertyUpdateRequest
from app.domain.auth.models import AuthSession, User, UserFavorite
from app.domain.auth.schemas import CreateUserRequest, UpdateUserRequest, UserSchema
from app.domain.chat.models import ChatMessage, ChatSession
from app.domain.property.models import Property
from app.domain.property.schemas import PropertySchema
from app.infrastructure.database.session import get_db
from app.config.settings import settings
from app.infrastructure.security.passwords import hash_password

router = APIRouter(prefix="/admin", tags=["admin"])


async def audit(db: AsyncSession, admin: User, action: str, resource_type: str, resource_id: str | None, details: dict) -> None:
    db.add(AdminAuditLog(admin_user_id=admin.id, action=action, resource_type=resource_type, resource_id=resource_id, details=details))
    await db.flush()


@router.get("/stats", response_model=AdminStatsResponse)
async def stats(_: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    total_properties = (await db.execute(select(func.count()).select_from(Property))).scalar_one()
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    total_conversations = (await db.execute(select(func.count()).select_from(ChatSession))).scalar_one()
    total_messages = (await db.execute(select(func.count()).select_from(ChatMessage))).scalar_one()
    total_favorites = (await db.execute(select(func.count()).select_from(UserFavorite))).scalar_one()
    # A zero-result search is represented by assistant message result_count=0.
    zero_results = (await db.execute(select(func.count()).select_from(ChatMessage).where(ChatMessage.role == "assistant", ChatMessage.result_count == 0))).scalar_one()
    return AdminStatsResponse(
        total_properties=total_properties, total_users=total_users, total_conversations=total_conversations,
        total_messages=total_messages, total_favorites=total_favorites, recent_zero_result_searches=zero_results,
    )


@router.get("/properties")
async def list_admin_properties(
    _: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db),
    q: str | None = Query(default=None), limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
):
    stmt = select(Property).order_by(Property.id.desc()).limit(limit).offset(offset)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Property.title.ilike(like)) | (Property.city.ilike(like)) | (Property.neighbourhood.ilike(like)))
    rows = (await db.execute(stmt)).scalars().all()
    ids = [p.id for p in rows]
    ownership_rows = (await db.execute(select(PropertyOwnership).where(PropertyOwnership.property_id.in_(ids)))).scalars().all() if ids else []
    owners = {o.property_id: OwnershipResponse.model_validate(o) for o in ownership_rows}
    flags_rows = (await db.execute(select(PropertyFlags).where(PropertyFlags.property_id.in_(ids)))).scalars().all() if ids else []
    flags = {f.property_id: f for f in flags_rows}
    return {"items": [PropertySchema.model_validate(p).model_dump() | {"ownership": owners.get(p.id).model_dump() if p.id in owners else None, "flags": {"is_published": flags[p.id].is_published, "is_featured": flags[p.id].is_featured, "is_archived": flags[p.id].is_archived} if p.id in flags else {"is_published": True, "is_featured": False, "is_archived": False}} for p in rows]}


@router.post("/properties", response_model=PropertySchema, status_code=status.HTTP_201_CREATED)
async def create_property(body: PropertyCreateRequest, admin: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    property_id = body.id
    if property_id is None:
        max_id = (await db.execute(select(func.max(Property.id)))).scalar_one()
        property_id = int(max_id or 0) + 1
    elif await db.get(Property, property_id):
        raise HTTPException(status_code=409, detail="Property ID already exists")
    prop = Property(
        id=property_id, title=body.title, city=body.city, neighbourhood=body.neighbourhood,
        intent=body.intent, price=body.price, bedrooms=body.bedrooms, bathrooms=body.bathrooms,
        size_sqm=body.size_sqm, property_type=body.property_type, distance_from_city_km=body.distance_from_city_km,
        description=body.description,
    )
    db.add(prop)
    if body.ownership:
        o = body.ownership
        db.add(PropertyOwnership(property_id=property_id, owner_type=o.owner_type, owner_id=o.owner_id, owner_name=o.owner_name, owner_email=o.owner_email))
    await audit(db, admin, "CREATE", "property", str(property_id), {"title": body.title})
    await db.commit()
    return PropertySchema.model_validate(prop)


@router.patch("/properties/{property_id}", response_model=PropertySchema)
async def update_property(property_id: int, body: PropertyUpdateRequest, admin: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    prop = await db.get(Property, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    before = {k: getattr(prop, k) for k in ["title", "city", "neighbourhood", "intent", "price", "bedrooms", "bathrooms", "size_sqm", "property_type", "distance_from_city_km", "description"]}
    updates = body.model_dump(exclude_none=True, exclude={"ownership"})
    for key, value in updates.items():
        setattr(prop, key, value)
    if body.ownership:
        o = body.ownership
        owner = await db.get(PropertyOwnership, property_id)
        if owner:
            owner.owner_type, owner.owner_id, owner.owner_name, owner.owner_email = o.owner_type, o.owner_id, o.owner_name, o.owner_email
        else:
            db.add(PropertyOwnership(property_id=property_id, owner_type=o.owner_type, owner_id=o.owner_id, owner_name=o.owner_name, owner_email=o.owner_email))
    await audit(db, admin, "UPDATE", "property", str(property_id), {"before": before, "updates": updates})
    await db.commit()
    await db.refresh(prop)
    return PropertySchema.model_validate(prop)


@router.patch("/properties/{property_id}/flags")
async def update_property_flags(property_id: int, body: dict, admin: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    if not await db.get(Property, property_id):
        raise HTTPException(status_code=404, detail="Property not found")
    row = await db.get(PropertyFlags, property_id)
    if not row:
        row = PropertyFlags(property_id=property_id)
        db.add(row)
    for key in ("is_published", "is_featured", "is_archived"):
        if key in body:
            setattr(row, key, bool(body[key]))
    await audit(db, admin, "UPDATE", "property_flags", str(property_id), body)
    await db.commit()
    return {"property_id": property_id, "is_published": row.is_published, "is_featured": row.is_featured, "is_archived": row.is_archived}


@router.delete("/properties/{property_id}")
async def delete_property(property_id: int, admin: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    prop = await db.get(Property, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    await audit(db, admin, "DELETE", "property", str(property_id), {"title": prop.title})
    await db.delete(prop)
    await db.commit()
    return {"deleted": True, "property_id": property_id}


@router.get("/users", response_model=list[UserSchema])
async def list_users(_: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db), q: str | None = Query(default=None), limit: int = Query(default=100, ge=1, le=200)):
    stmt = select(User).order_by(User.created_at.desc()).limit(limit)
    if q:
        stmt = stmt.where(User.email.ilike(f"%{q}%"))
    return [UserSchema.model_validate(row) for row in (await db.execute(stmt)).scalars().all()]


@router.post("/users", response_model=UserSchema, status_code=201)
async def create_user(body: CreateUserRequest, admin: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    existing = (await db.execute(select(User).where(User.email == body.email.lower()))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")
    if body.role == "ADMIN":
        admin_exists = (await db.execute(select(func.count()).select_from(User).where(User.role == "ADMIN"))).scalar_one()
        if admin_exists:
            raise HTTPException(status_code=400, detail="This POC supports exactly one admin account")
    user = User(email=body.email.lower(), password_hash=hash_password(body.password), role=body.role, email_verified=body.email_verified, profile={"full_name": body.full_name} if body.full_name else {})
    db.add(user)
    await db.flush()
    await audit(db, admin, "CREATE", "user", user.id, {"email": user.email, "role": user.role})
    await db.commit()
    return UserSchema.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserSchema)
async def update_user(user_id: str, body: UpdateUserRequest, admin: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id and body.is_active is False:
        raise HTTPException(status_code=400, detail="The only admin cannot disable itself")
    old = {"role": user.role, "is_active": user.is_active, "profile": user.profile}
    if body.role and body.role != user.role:
        if body.role == "ADMIN":
            admin_exists = (await db.execute(select(func.count()).select_from(User).where(User.role == "ADMIN", User.id != user.id))).scalar_one()
            if admin_exists:
                raise HTTPException(status_code=400, detail="This POC supports exactly one admin account")
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.full_name is not None:
        user.profile = {**(user.profile or {}), "full_name": body.full_name}
    await audit(db, admin, "UPDATE", "user", user.id, {"before": old})
    if body.is_active is False:
        await db.execute(update(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).values(revoked_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc)))
    await db.commit()
    return UserSchema.model_validate(user)


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="The only admin cannot delete itself")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await audit(db, admin, "DELETE", "user", user.id, {"email": user.email})
    await db.delete(user)
    await db.commit()
    return {"deleted": True}


@router.get("/conversations")
async def conversations(_: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db), limit: int = Query(default=50, ge=1, le=200)):
    rows = (await db.execute(select(ChatSession).order_by(ChatSession.last_active.desc()).limit(limit))).scalars().all()
    return [{"session_id": r.session_id, "user_id": r.user_id, "created_at": r.created_at, "last_active": r.last_active, "memory": r.memory} for r in rows]


@router.get("/conversations/{session_id}")
async def conversation_detail(session_id: str, _: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    session = await db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Conversation not found")
    rows = (await db.execute(select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at))).scalars().all()
    return {"session": {"session_id": session.session_id, "user_id": session.user_id, "memory": session.memory}, "messages": [{"id": r.id, "role": r.role, "content": r.content, "intent": r.intent, "result_count": r.result_count, "created_at": r.created_at} for r in rows]}


@router.get("/audit-log", response_model=list[AuditLogResponse])
async def audit_log(_: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db), limit: int = Query(default=100, ge=1, le=200)):
    rows = (await db.execute(select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(limit))).scalars().all()
    return [AuditLogResponse.model_validate(r) for r in rows]


@router.get("/settings/llm")
async def llm_settings(_: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(AdminSetting).where(AdminSetting.key.like("llm.%")))).scalars().all()
    values = {r.key.removeprefix("llm."): r.value for r in rows}
    if "api_key" in values:
        values["api_key_set"] = "true"
        values["api_key"] = ""
    return values


@router.put("/settings/llm")
async def update_llm_settings(body: dict, admin: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    allowed = {"provider", "model", "base_url", "temperature", "max_tokens", "api_key"}
    values = {k: v for k, v in body.items() if k in allowed and v is not None and not (k == "api_key" and str(v).strip() == "")}
    if "temperature" in values:
        values["temperature"] = str(float(values["temperature"]))
    if "max_tokens" in values:
        values["max_tokens"] = str(int(values["max_tokens"]))
    for key, value in values.items():
        row = await db.get(AdminSetting, f"llm.{key}")
        if row:
            row.value = str(value)
            row.updated_by = admin.id
        else:
            db.add(AdminSetting(key=f"llm.{key}", value=str(value), updated_by=admin.id))
    await audit(db, admin, "UPDATE", "llm_settings", None, {"changed_keys": list(values)})
    await db.commit()
    from app.infrastructure.llm.factory import create_llm_provider, set_llm_provider
    merged = {k: r.value for k, r in {row.key.removeprefix("llm."): row for row in (await db.execute(select(AdminSetting).where(AdminSetting.key.like("llm.%")))).scalars().all()}.items()}
    set_llm_provider(create_llm_provider(merged.get("provider"), merged.get("model"), merged.get("api_key"), merged.get("base_url"), float(merged.get("temperature", settings.LLM_TEMPERATURE)), int(merged.get("max_tokens", settings.LLM_MAX_TOKENS))))
    return {"updated": list(values)}
