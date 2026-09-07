from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.api.dependencies import get_current_user
from app.domain.auth.models import RecentlyViewedProperty, SavedSearch, User, UserFavorite
from app.domain.chat.models import ChatSession
from app.infrastructure.database.session import get_db

router = APIRouter(prefix="/account", tags=["account"])


class SearchSaveRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    criteria: dict


@router.get("/favorites")
async def favorites(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.execute(select(UserFavorite.property_id).where(UserFavorite.user_id == user.id).order_by(UserFavorite.created_at.desc()))
    return {"property_ids": list(rows.scalars().all())}


@router.post("/favorites/{property_id}", status_code=201)
async def add_favorite(property_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    exists = await db.get(UserFavorite, {"user_id": user.id, "property_id": property_id})
    if not exists:
        db.add(UserFavorite(user_id=user.id, property_id=property_id))
        await db.commit()
    return {"saved": True, "property_id": property_id}


@router.delete("/favorites/{property_id}")
async def remove_favorite(property_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(delete(UserFavorite).where(UserFavorite.user_id == user.id, UserFavorite.property_id == property_id))
    await db.commit()
    return {"saved": False, "property_id": property_id}


@router.get("/saved-searches")
async def saved_searches(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.execute(select(SavedSearch).where(SavedSearch.user_id == user.id).order_by(SavedSearch.updated_at.desc()))
    return {"items": [{"id": r.id, "name": r.name, "criteria": r.criteria, "created_at": r.created_at, "updated_at": r.updated_at} for r in rows.scalars().all()]}


@router.post("/saved-searches", status_code=201)
async def save_search(body: SearchSaveRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = SavedSearch(user_id=user.id, name=body.name, criteria=body.criteria)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"id": row.id, "name": row.name, "criteria": row.criteria}


@router.delete("/saved-searches/{search_id}")
async def delete_search(search_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(delete(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.user_id == user.id))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Saved search not found")
    await db.commit()
    return {"deleted": True}


@router.get("/recently-viewed")
async def recently_viewed(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.execute(select(RecentlyViewedProperty).where(RecentlyViewedProperty.user_id == user.id).order_by(RecentlyViewedProperty.viewed_at.desc()).limit(20))
    return {"property_ids": [r.property_id for r in rows.scalars().all()]}


@router.post("/recently-viewed/{property_id}")
async def add_recently_viewed(property_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await db.get(RecentlyViewedProperty, {"user_id": user.id, "property_id": property_id})
    if row:
        from datetime import datetime, timezone
        row.viewed_at = datetime.now(timezone.utc)
    else:
        db.add(RecentlyViewedProperty(user_id=user.id, property_id=property_id))
    await db.commit()
    return {"tracked": True}


@router.delete("/me")
async def delete_my_account(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(delete(ChatSession).where(ChatSession.user_id == user.id))
    await db.delete(user)
    await db.commit()
    return {"deleted": True}
