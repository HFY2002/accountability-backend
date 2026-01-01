from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from uuid import UUID

from app.api import deps
from app.db import models
from app.schemas import social as social_schemas
from app.schemas.goal_viewers import AllowedViewerAddIn

router = APIRouter()

@router.get("/goals/{goal_id}/allowed-viewers", response_model=list[social_schemas.FriendOut])
async def get_goal_allowed_viewers(
    goal_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    Get all users who are allowed to view and verify a specific goal.
    Only the goal owner can view this list.
    """
    # Verify the goal exists and belongs to current user
    goal_stmt = select(models.Goal).where(
        models.Goal.id == goal_id,
        models.Goal.user_id == current_user.id
    )
    goal_result = await db.execute(goal_stmt)
    goal = goal_result.scalars().first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found or you don't have permission")
    
    # Get allowed viewers and their user details
    viewers_stmt = select(models.GoalAllowedViewer).where(
        models.GoalAllowedViewer.goal_id == goal_id
    )
    viewers_result = await db.execute(viewers_stmt)
    allowed_viewers = viewers_result.scalars().all()
    
    # Transform to FriendOut format
    viewers_list = []
    for viewer in allowed_viewers:
        user_stmt = select(models.User).where(models.User.id == viewer.user_id)
        user_result = await db.execute(user_stmt)
        user = user_result.scalars().first()
        
        if user:
            # Get profile for avatar
            profile_stmt = select(models.UserProfile).where(
                models.UserProfile.user_id == viewer.user_id
            )
            profile_result = await db.execute(profile_stmt)
            profile = profile_result.scalars().first()
            
            viewers_list.append(social_schemas.FriendOut(
                id=str(viewer.user_id),  # Use user ID instead of viewer relationship ID
                user_id=str(user.id),
                name=user.username,
                email=user.email,
                avatar=profile.avatar_url if profile else None,
                status="accepted",  # Since they're allowed viewers, treat as accepted
                added_at=None  # Not tracking when viewers were added
            ))
    
    return viewers_list


@router.post("/goals/{goal_id}/allowed-viewers", response_model=social_schemas.FriendOut)
async def add_goal_allowed_viewer(
    goal_id: UUID,
    viewer_data: AllowedViewerAddIn,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    Add a friend as an allowed viewer for a goal.
    Only the goal owner can add viewers.
    """
    # Verify the goal exists and belongs to current user
    goal_stmt = select(models.Goal).where(
        models.Goal.id == goal_id,
        models.Goal.user_id == current_user.id
    )
    goal_result = await db.execute(goal_stmt)
    goal = goal_result.scalars().first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found or you don't have permission")
    
    # Verify that viewer_id is a friend
    friendship_stmt = select(models.Friend).where(
        or_(
            and_(
                models.Friend.requester_id == current_user.id,
                models.Friend.addressee_id == viewer_data.viewer_id,
                models.Friend.status == models.FriendStatus.accepted
            ),
            and_(
                models.Friend.requester_id == viewer_data.viewer_id,
                models.Friend.addressee_id == current_user.id,
                models.Friend.status == models.FriendStatus.accepted
            )
        )
    )
    friendship_result = await db.execute(friendship_stmt)
    friendship = friendship_result.scalars().first()
    
    if not friendship:
        raise HTTPException(status_code=400, detail="You can only add friends as allowed viewers")
    
    # Check if already added
    existing_stmt = select(models.GoalAllowedViewer).where(
        models.GoalAllowedViewer.goal_id == goal_id,
        models.GoalAllowedViewer.user_id == viewer_data.viewer_id
    )
    existing_result = await db.execute(existing_stmt)
    if existing_result.scalars().first():
        raise HTTPException(status_code=400, detail="User is already an allowed viewer")
    
    # Add the viewer
    allowed_viewer = models.GoalAllowedViewer(
        goal_id=goal_id,
        user_id=viewer_data.viewer_id,
        can_verify=True
    )
    db.add(allowed_viewer)
    await db.commit()
    
    # Get user details for response
    user_stmt = select(models.User).where(models.User.id == viewer_data.viewer_id)
    user_result = await db.execute(user_stmt)
    user = user_result.scalars().first()
    
    profile_stmt = select(models.UserProfile).where(
        models.UserProfile.user_id == viewer_data.viewer_id
    )
    profile_result = await db.execute(profile_stmt)
    profile = profile_result.scalars().first()
    
    return social_schemas.FriendOut(
        id=str(user.id),
        user_id=str(user.id),
        name=user.username,
        email=user.email,
        avatar=profile.avatar_url if profile else None,
        status="accepted",
        added_at=None
    )


@router.delete("/goals/{goal_id}/allowed-viewers/{viewer_id}", status_code=204)
async def remove_goal_allowed_viewer(
    goal_id: UUID,
    viewer_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    Remove a user from the allowed viewers list for a goal.
    Only the goal owner can remove viewers.
    """
    # Verify the goal exists and belongs to current user
    goal_stmt = select(models.Goal).where(
        models.Goal.id == goal_id,
        models.Goal.user_id == current_user.id
    )
    goal_result = await db.execute(goal_stmt)
    goal = goal_result.scalars().first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found or you don't have permission")
    
    # Find and remove the viewer
    viewer_stmt = select(models.GoalAllowedViewer).where(
        models.GoalAllowedViewer.goal_id == goal_id,
        models.GoalAllowedViewer.user_id == viewer_id
    )
    viewer_result = await db.execute(viewer_stmt)
    viewer = viewer_result.scalars().first()
    
    if not viewer:
        raise HTTPException(status_code=404, detail="Viewer not found")
    
    await db.delete(viewer)
    await db.commit()
    
    return None


@router.get("/goals/{goal_id}/can-upload-proof", response_model=dict)
async def check_can_upload_proof(
    goal_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    Check if the current user can upload proof for a goal.
    Returns allowed viewers count for verification requirements.
    """
    # Get the goal
    goal_stmt = select(models.Goal).where(models.Goal.id == goal_id)
    goal_result = await db.execute(goal_stmt)
    goal = goal_result.scalars().first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    # Check if user owns the goal
    if goal.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only goal owner can upload proofs")
    
    # Calculate required verifications based on privacy
    required = 1
    if goal.privacy_setting == models.GoalPrivacy.select_friends:
        viewer_count_stmt = select(func.count()).where(
            models.GoalAllowedViewer.goal_id == goal.id,
            models.GoalAllowedViewer.can_verify == True
        )
        viewer_count_result = await db.execute(viewer_count_stmt)
        required = viewer_count_result.scalar() or 1
    elif goal.privacy_setting == models.GoalPrivacy.friends:
        friend_count_stmt = select(func.count()).where(
            or_(
                models.Friend.requester_id == current_user.id,
                models.Friend.addressee_id == current_user.id
            ),
            models.Friend.status == models.FriendStatus.accepted
        )
        friend_count_result = await db.execute(friend_count_stmt)
        required = friend_count_result.scalar() or 1
    
    return {
        "can_upload": True,
        "required_verifications": required,
        "privacy_setting": goal.privacy_setting
    }