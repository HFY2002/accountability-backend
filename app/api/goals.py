from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from typing import Union, List
from datetime import datetime
from app.api import deps
from app.schemas import goal as schemas
from app.db import models

router = APIRouter()

@router.post("", response_model=schemas.GoalDetailOut)
async def create_goal(
    goal_in: Union[schemas.GoalCreateFlexibleIn, schemas.GoalCreateDefinedIn],
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    # 1. Create Goal Record
    db_goal = models.Goal(
        user_id=current_user.id,
        title=goal_in.title,
        description=goal_in.description,
        start_date=goal_in.start_date,
        deadline=goal_in.deadline,
        privacy_setting=goal_in.privacy_setting,
        image_url=goal_in.image_url,
        user_story=goal_in.user_story,
        milestone_type=goal_in.milestone_type,
        milestone_interval_days=goal_in.milestone_interval_days,
    )
    
    if goal_in.milestone_type == "defined":
        db_goal.milestone_quantity = goal_in.milestone_quantity
        db_goal.milestone_unit = goal_in.milestone_unit

    db.add(db_goal)
    await db.flush()

    # 2. Generate Milestones
    milestones_to_add = []
    
    if goal_in.milestone_type == "flexible":
        # User defined start milestones
        for m in goal_in.initial_milestones:
            milestone = models.Milestone(
                goal_id=db_goal.id,
                title=m.title,
                description=m.description,
                is_flexible=True,
                batch_number=1,
                order_index=m.order_index,
                due_date=m.due_date 
            )
            milestones_to_add.append(milestone)
    
    elif goal_in.milestone_type == "defined":
        # Auto-calculate based on interval and deadline
        import math
        from datetime import timedelta
        
        total_days = (goal_in.deadline - goal_in.start_date).days
        num_milestones = math.ceil(total_days / goal_in.milestone_interval_days)
        
        for i in range(num_milestones):
            due_date = goal_in.start_date + timedelta(days=(i+1)*goal_in.milestone_interval_days)
            milestone = models.Milestone(
                goal_id=db_goal.id,
                title=f"Complete {goal_in.milestone_quantity} {goal_in.milestone_unit}",
                is_flexible=False,
                order_index=i,
                due_date=due_date
            )
            milestones_to_add.append(milestone)

    db.add_all(milestones_to_add)
    
    # 3. Handle selected friends for select_friends privacy
    if goal_in.privacy_setting == models.GoalPrivacy.select_friends and hasattr(goal_in, 'selected_friend_ids') and goal_in.selected_friend_ids:
        # Validate each friend is actually a friend
        for friend_id in goal_in.selected_friend_ids:
            # Check if they are friends
            friend_stmt = select(models.Friend).where(
                or_(
                    and_(
                        models.Friend.requester_id == current_user.id,
                        models.Friend.addressee_id == friend_id,
                        models.Friend.status == models.FriendStatus.accepted
                    ),
                    and_(
                        models.Friend.requester_id == friend_id,
                        models.Friend.addressee_id == current_user.id,
                        models.Friend.status == models.FriendStatus.accepted
                    )
                )
            )
            friend_result = await db.execute(friend_stmt)
            friendship = friend_result.scalars().first()
            
            if friendship:
                # Add as allowed viewer
                allowed_viewer = models.GoalAllowedViewer(
                    goal_id=db_goal.id,
                    user_id=friend_id,
                    can_verify=True
                )
                db.add(allowed_viewer)
            else:
                # Log warning but don't fail - friend might have been removed
                print(f"Warning: User {friend_id} is not a friend of {current_user.id}, skipping")
    
    await db.commit()
    
    # Query the goal with loaded milestones to avoid lazy loading issues
    stmt = select(models.Goal).where(
        models.Goal.id == db_goal.id
    ).options(selectinload(models.Goal.milestones))
    
    result = await db.execute(stmt)
    goal_with_milestones = result.scalars().first()
    
    # Build verifying_partners list
    verifying_partners = []
    if (goal_in.privacy_setting == models.GoalPrivacy.select_friends and 
        hasattr(goal_in, 'selected_friend_ids') and 
        goal_in.selected_friend_ids):
        
        for friend_id in goal_in.selected_friend_ids:
            # Get user details
            user_stmt = select(models.User).where(models.User.id == friend_id)
            user_result = await db.execute(user_stmt)
            user = user_result.scalars().first()
            
            if user:
                # Get profile
                profile_stmt = select(models.UserProfile).where(
                    models.UserProfile.user_id == friend_id
                )
                profile_result = await db.execute(profile_stmt)
                profile = profile_result.scalars().first()
                
                verifying_partners.append(schemas.UserSummaryOut(
                    id=user.id,
                    username=user.username,
                    email=user.email,
                    avatar_url=profile.avatar_url if profile else None
                ))
    
    # Return with verifying partners
    return schemas.GoalDetailOut(
        id=goal_with_milestones.id,
        user_id=goal_with_milestones.user_id,
        title=goal_with_milestones.title,
        description=goal_with_milestones.description,
        milestone_type=goal_with_milestones.milestone_type,
        status=goal_with_milestones.status,
        is_completed=goal_with_milestones.is_completed,
        milestones=goal_with_milestones.milestones,
        start_date=goal_with_milestones.start_date,
        deadline=goal_with_milestones.deadline,
        privacy_setting=goal_with_milestones.privacy_setting,
        image_url=goal_with_milestones.image_url,
        milestone_quantity=goal_with_milestones.milestone_quantity,
        milestone_unit=goal_with_milestones.milestone_unit,
        user_story=goal_with_milestones.user_story,
        verifying_partners=verifying_partners if verifying_partners else None
    )

@router.get("", response_model=List[schemas.GoalListOut])
async def list_goals(
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """List all goals for the current user"""
    stmt = select(models.Goal).where(
        models.Goal.user_id == current_user.id,
        models.Goal.status != models.GoalStatus.archived
    ).order_by(models.Goal.created_at.desc())
    
    result = await db.execute(stmt)
    goals = result.scalars().all()
    return goals


@router.get("/{goal_id}", response_model=schemas.GoalDetailOut)
async def get_goal(
    goal_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """Get detailed information about a specific goal"""
    stmt = select(models.Goal).where(
        models.Goal.id == goal_id,
        models.Goal.user_id == current_user.id
    ).options(selectinload(models.Goal.milestones))
    
    result = await db.execute(stmt)
    goal = result.scalars().first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    # Load verifying partners
    verifying_partners = []
    if goal.privacy_setting == models.GoalPrivacy.select_friends:
        viewers_stmt = select(models.GoalAllowedViewer).where(
            models.GoalAllowedViewer.goal_id == goal_id,
            models.GoalAllowedViewer.can_verify == True
        )
        viewers_result = await db.execute(viewers_stmt)
        allowed_viewers = viewers_result.scalars().all()
        
        for viewer in allowed_viewers:
            user_stmt = select(models.User).where(models.User.id == viewer.user_id)
            user_result = await db.execute(user_stmt)
            user = user_result.scalars().first()
            
            if user:
                # Get profile
                profile_stmt = select(models.UserProfile).where(
                    models.UserProfile.user_id == viewer.user_id
                )
                profile_result = await db.execute(profile_stmt)
                profile = profile_result.scalars().first()
                
                verifying_partners.append(schemas.UserSummaryOut(
                    id=user.id,
                    username=user.username,
                    email=user.email,
                    avatar_url=profile.avatar_url if profile else None
                ))
    
    # Return with verifying partners
    return schemas.GoalDetailOut(
        id=goal.id,
        user_id=goal.user_id,
        title=goal.title,
        description=goal.description,
        milestone_type=goal.milestone_type,
        status=goal.status,
        is_completed=goal.is_completed,
        milestones=goal.milestones,
        start_date=goal.start_date,
        deadline=goal.deadline,
        privacy_setting=goal.privacy_setting,
        image_url=goal.image_url,
        milestone_quantity=goal.milestone_quantity,
        milestone_unit=goal.milestone_unit,
        user_story=goal.user_story,
        verifying_partners=verifying_partners if verifying_partners else None
    )


@router.put("/{goal_id}", response_model=schemas.GoalDetailOut)
async def update_goal(
    goal_id: str,
    goal_in: schemas.GoalUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """Update a goal's information"""
    stmt = select(models.Goal).where(
        models.Goal.id == goal_id,
        models.Goal.user_id == current_user.id
    ).options(selectinload(models.Goal.milestones))
    
    result = await db.execute(stmt)
    db_goal = result.scalars().first()
    
    if not db_goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    update_data = goal_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_goal, field, value)
    
    # Handle privacy setting change and selected friends
    if 'privacy_setting' in update_data or 'selected_friend_ids' in update_data:
        new_privacy = update_data.get('privacy_setting', db_goal.privacy_setting)
        
        if new_privacy == models.GoalPrivacy.select_friends:
            # Get selected friend IDs from the request
            selected_friend_ids = update_data.get('selected_friend_ids', [])
            
            # Remove existing allowed viewers
            delete_stmt = select(models.GoalAllowedViewer).where(
                models.GoalAllowedViewer.goal_id == goal_id
            )
            existing_viewers = (await db.execute(delete_stmt)).scalars().all()
            for viewer in existing_viewers:
                await db.delete(viewer)
            
            # Add new allowed viewers
            for friend_id in selected_friend_ids:
                # Validate each friend is actually a friend
                friend_stmt = select(models.Friend).where(
                    or_(
                        and_(
                            models.Friend.requester_id == current_user.id,
                            models.Friend.addressee_id == friend_id,
                            models.Friend.status == models.FriendStatus.accepted
                        ),
                        and_(
                            models.Friend.requester_id == friend_id,
                            models.Friend.addressee_id == current_user.id,
                            models.Friend.status == models.FriendStatus.accepted
                        )
                    )
                )
                friend_result = await db.execute(friend_stmt)
                friendship = friend_result.scalars().first()
                
                if friendship:
                    # Add as allowed viewer
                    allowed_viewer = models.GoalAllowedViewer(
                        goal_id=goal_id,
                        user_id=friend_id,
                        can_verify=True
                    )
                    db.add(allowed_viewer)
        
        # If privacy is NOT select_friends, clean up allowed viewers
        elif new_privacy != models.GoalPrivacy.select_friends:
            delete_stmt = select(models.GoalAllowedViewer).where(
                models.GoalAllowedViewer.goal_id == goal_id
            )
            existing_viewers = (await db.execute(delete_stmt)).scalars().all()
            for viewer in existing_viewers:
                await db.delete(viewer)
    
    await db.commit()
    await db.refresh(db_goal)
    
    # Reload with milestones to ensure proper serialization
    stmt = select(models.Goal).where(
        models.Goal.id == goal_id
    ).options(selectinload(models.Goal.milestones))
    
    result = await db.execute(stmt)
    updated_goal = result.scalars().first()
    
    return updated_goal


@router.delete("/{goal_id}")
async def delete_goal(
    goal_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """Soft delete a goal (archive it)"""
    stmt = select(models.Goal).where(
        models.Goal.id == goal_id,
        models.Goal.user_id == current_user.id
    )
    result = await db.execute(stmt)
    goal = result.scalars().first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    # Soft delete by archiving
    goal.status = models.GoalStatus.archived
    await db.commit()
    
    return {"message": "Goal deleted successfully"}


@router.post("/{goal_id}/complete")
async def mark_goal_complete(
    goal_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """Mark a goal as complete (pending verification if needed)"""
    stmt = select(models.Goal).where(
        models.Goal.id == goal_id,
        models.Goal.user_id == current_user.id
    )
    result = await db.execute(stmt)
    goal = result.scalars().first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    # Check if goal has verifying partners
    has_viewers = await db.execute(
        select(models.GoalAllowedViewer).where(
            models.GoalAllowedViewer.goal_id == goal_id
        )
    )
    if has_viewers.scalars().first():
        goal.status = models.GoalStatus.completed_pending
    else:
        goal.status = models.GoalStatus.completed_verified
    
    goal.is_completed = True
    goal.completed_at = datetime.utcnow()
    
    await db.commit()
    return {"message": "Goal marked as complete", "status": goal.status}


@router.post("/{goal_id}/give-up")
async def give_up_goal(
    goal_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """Mark a goal as failed/given up"""
    stmt = select(models.Goal).where(
        models.Goal.id == goal_id,
        models.Goal.user_id == current_user.id
    )
    result = await db.execute(stmt)
    goal = result.scalars().first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    goal.status = models.GoalStatus.failed
    goal.is_completed = True
    goal.completed_at = datetime.utcnow()

    await db.commit()
    return {"message": "Goal marked as failed", "status": goal.status}


@router.patch("/milestones/{milestone_id}/complete")
async def complete_milestone(
    milestone_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    Mark a milestone as completed.
    This is typically called automatically when a proof gets enough verifications.
    """
    stmt = select(models.Milestone).where(
        models.Milestone.id == milestone_id
    )
    result = await db.execute(stmt)
    milestone = result.scalars().first()
    
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    
    # Verify user owns the goal this milestone belongs to
    goal_stmt = select(models.Goal).where(
        models.Goal.id == milestone.goal_id,
        models.Goal.user_id == current_user.id
    )
    goal_result = await db.execute(goal_stmt)
    goal = goal_result.scalars().first()
    
    if not goal:
        raise HTTPException(status_code=403, detail="You don't have permission to update this milestone")
    
    # Mark milestone as completed
    milestone.completed = True
    milestone.completed_at = datetime.utcnow()
    milestone.progress = 100
    
    await db.commit()
    await db.refresh(milestone)
    
    return {
        "message": "Milestone marked as complete",
        "milestone_id": milestone.id,
        "completed": milestone.completed,
        "completed_at": milestone.completed_at
    }