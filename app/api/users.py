from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
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
    
    # Mark onboarding as complete
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


@router.get("/search", response_model=List[schemas.UserSearchResult])
async def search_users(
    email: str = Query(..., description="Email to search for"),
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Search for users by email to add as friends.
    Returns users that match the email query, along with friendship status.
    """
    # Search for users matching the email
    search_stmt = select(models.User).where(
        models.User.email.ilike(f"%{email}%"),
        models.User.id != current_user.id  # Don't return current user
    ).limit(10)
    
    result = await db.execute(search_stmt)
    matching_users = result.scalars().all()
    
    if not matching_users:
        return []
    
    # Get current user's friendships to determine status
    friendships_stmt = select(models.Friend).where(
        or_(
            models.Friend.requester_id == current_user.id,
            models.Friend.addressee_id == current_user.id
        )
    )
    friendships_result = await db.execute(friendships_stmt)
    friendships = friendships_result.scalars().all()
    
    # Create a dict for quick lookup
    friendship_map = {}
    for friendship in friendships:
        other_user_id = (friendship.addressee_id if friendship.requester_id == current_user.id else friendship.requester_id)
        friendship_map[other_user_id] = friendship
    
    results = []
    for user in matching_users:
        # Get the user's profile
        profile_stmt = select(models.UserProfile).where(models.UserProfile.user_id == user.id)
        profile_result = await db.execute(profile_stmt)
        profile = profile_result.scalars().first()
        
        # Determine friendship status
        is_friend = False
        has_pending_request = False
        if user.id in friendship_map:
            friendship = friendship_map[user.id]
            if friendship.status == models.FriendStatus.accepted:
                is_friend = True
            elif friendship.status == models.FriendStatus.pending:
                has_pending_request = True
        
        results.append(schemas.UserSearchResult(
            id=user.id,
            email=user.email,
            username=user.username,
            avatar_url=profile.avatar_url if profile else None,
            is_friend=is_friend,
            has_pending_request=has_pending_request
        ))
    
    return results
