from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db import models
from app.api import deps
from app.schemas import user as schemas
from app.api.deps import get_current_user

router = APIRouter()


async def get_profile_by_user_id(db: AsyncSession, user_id: str):
    result = await db.execute(
        select(models.UserProfile).where(models.UserProfile.user_id == user_id)
    )
    return result.scalars().first()


@router.get("/profile", response_model=schemas.UserProfileOut)
async def get_profile(
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(deps.get_db)
):
    profile = await get_profile_by_user_id(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.put("/profile", response_model=schemas.UserProfileOut)
async def update_profile(
    profile_update: schemas.UserProfileUpdate,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(deps.get_db)
):
    profile = await get_profile_by_user_id(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    update_data = profile_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)
    
    await db.commit()
    await db.refresh(profile)
    return profile


@router.post("/profile/interests", response_model=schemas.UserProfileOut)
async def set_interests(
    interests: schemas.UserInterestsUpdate,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(deps.get_db)
):
    profile = await get_profile_by_user_id(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Get category IDs from names
    category_ids = []
    for category_name in interests.category_names:
        result = await db.execute(
            select(models.GoalCategory.id).where(models.GoalCategory.name == category_name)
        )
        category = result.scalars().first()
        if category:
            category_ids.append(category)
    
    # In a real app, store these interests properly
    # For now, just mark onboarding as complete
    profile.onboarding_completed = True
    await db.commit()
    await db.refresh(profile)
    return profile


# Frontend compatibility endpoint - interests at root level
@router.post("/interests", response_model=schemas.UserProfileOut)
async def set_interests_frontend(
    interests: schemas.UserInterestsUpdate,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(deps.get_db),
):
    """
    Frontend compatibility endpoint for setting user interests.
    This matches the frontend's expected /users/interests endpoint.
    """
    return await set_interests(interests, current_user, db)


@router.get("/me", response_model=schemas.UserOut)
async def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user
