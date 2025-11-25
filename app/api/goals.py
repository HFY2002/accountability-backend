from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
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
        category_id=goal_in.category_id,
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
    await db.commit()
    
    # Query the goal with loaded milestones to avoid lazy loading issues
    stmt = select(models.Goal).where(
        models.Goal.id == db_goal.id
    ).options(selectinload(models.Goal.milestones))
    
    result = await db.execute(stmt)
    goal_with_milestones = result.scalars().first()
    
    return goal_with_milestones

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
    
    return goal


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
