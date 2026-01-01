from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from uuid import UUID
from datetime import datetime, timezone

from app.api import deps
from app.schemas import interval_change as schemas
from app.db import models
from app.services.notification import create_notification

router = APIRouter()

@router.post("", response_model=schemas.IntervalChangeRequestOut)
async def create_interval_change_request(
    request_in: schemas.IntervalChangeRequestCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    Create an interval change request for a goal.
    Sends notifications to all accountability partners.
    """
    # 1. Validate goal exists and belongs to current user
    goal_stmt = select(models.Goal).where(
        models.Goal.id == request_in.goal_id,
        models.Goal.user_id == current_user.id
    )
    result = await db.execute(goal_stmt)
    goal = result.scalars().first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    # 2. Check goal is not private
    if goal.privacy_setting == models.GoalPrivacy.private:
        raise HTTPException(status_code=400, detail="Cannot request interval change for private goals")
    
    # 3. Check for existing pending request
    existing_stmt = select(models.IntervalChangeRequest).where(
        models.IntervalChangeRequest.goal_id == request_in.goal_id,
        models.IntervalChangeRequest.status == "pending"
    )
    existing_result = await db.execute(existing_stmt)
    if existing_result.scalars().first():
        raise HTTPException(status_code=400, detail="There is already a pending interval change request for this goal")
    
    # 4. Create the interval change request
    db_request = models.IntervalChangeRequest(
        goal_id=request_in.goal_id,
        requester_id=current_user.id,
        current_interval=goal.milestone_interval_days or 0,
        requested_interval=request_in.requested_interval,
        status="pending"
    )
    db.add(db_request)
    await db.flush()
    
    # 5. Send notifications to accountability partners
    if goal.privacy_setting == models.GoalPrivacy.select_friends:
        # Get allowed viewers
        viewers_stmt = select(models.GoalAllowedViewer).where(
            models.GoalAllowedViewer.goal_id == goal.id,
            models.GoalAllowedViewer.can_verify == True
        )
        viewers_result = await db.execute(viewers_stmt)
        viewers = viewers_result.scalars().all()
        
        for viewer in viewers:
            await create_notification(
                db,
                recipient_id=viewer.user_id,
                type=models.NotificationType.interval_change_request,
                message=f"{current_user.username} requested to change milestone interval for '{goal.title}' from {goal.milestone_interval_days or 0} to {request_in.requested_interval} days",
                actor_id=current_user.id,
                goal_id=goal.id
            )
    
    elif goal.privacy_setting == models.GoalPrivacy.friends:
        # Get all friends
        friends_stmt = select(models.Friend).where(
            or_(
                models.Friend.requester_id == current_user.id,
                models.Friend.addressee_id == current_user.id
            ),
            models.Friend.status == models.FriendStatus.accepted
        )
        friends_result = await db.execute(friends_stmt)
        friendships = friends_result.scalars().all()
        
        for friendship in friendships:
            friend_id = (friendship.addressee_id if friendship.requester_id == current_user.id 
                        else friendship.requester_id)
            
            await create_notification(
                db,
                recipient_id=friend_id,
                type=models.NotificationType.interval_change_request,
                message=f"{current_user.username} requested to change milestone interval for '{goal.title}' from {goal.milestone_interval_days or 0} to {request_in.requested_interval} days",
                actor_id=current_user.id,
                goal_id=goal.id
            )
    
    await db.commit()
    await db.refresh(db_request)
    
    return schemas.IntervalChangeRequestOut(
        id=db_request.id,
        goal_id=db_request.goal_id,
        goal_title=goal.title,
        requester_id=db_request.requester_id,
        requester_name=current_user.username,
        current_interval=db_request.current_interval,
        requested_interval=db_request.requested_interval,
        status=db_request.status,
        created_at=db_request.created_at
    )


@router.get("/pending", response_model=list[schemas.IntervalChangeRequestOut])
async def list_pending_interval_change_requests(
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    List all pending interval change requests that the current user can verify.
    These are requests from friends' goals where the user is an accountability partner.
    """
    pending_requests = []
    
    # Get requests from goals where current user is an allowed viewer
    viewer_goals_stmt = select(models.GoalAllowedViewer.goal_id).where(
        models.GoalAllowedViewer.user_id == current_user.id,
        models.GoalAllowedViewer.can_verify == True
    )
    viewer_goals_result = await db.execute(viewer_goals_stmt)
    viewer_goal_ids = [row[0] for row in viewer_goals_result.fetchall()]
    
    # Get pending requests for those goals
    if viewer_goal_ids:
        requests_stmt = select(models.IntervalChangeRequest).where(
            models.IntervalChangeRequest.goal_id.in_(viewer_goal_ids),
            models.IntervalChangeRequest.status == "pending"
        )
        requests_result = await db.execute(requests_stmt)
        requests = requests_result.scalars().all()
        
        for req in requests:
            # Get goal and requester details
            goal_stmt = select(models.Goal).where(models.Goal.id == req.goal_id)
            goal_result = await db.execute(goal_stmt)
            goal = goal_result.scalars().first()
            
            user_stmt = select(models.User).where(models.User.id == req.requester_id)
            user_result = await db.execute(user_stmt)
            user = user_result.scalars().first()
            
            if goal and user:
                pending_requests.append(schemas.IntervalChangeRequestOut(
                    id=req.id,
                    goal_id=req.goal_id,
                    goal_title=goal.title,
                    requester_id=req.requester_id,
                    requester_name=user.username,
                    current_interval=req.current_interval,
                    requested_interval=req.requested_interval,
                    status=req.status,
                    created_at=req.created_at
                ))
    
    # Also check for friends privacy goals
    friends_stmt = select(models.Friend).where(
        or_(
            models.Friend.requester_id == current_user.id,
            models.Friend.addressee_id == current_user.id
        ),
        models.Friend.status == models.FriendStatus.accepted
    )
    friends_result = await db.execute(friends_stmt)
    friendships = friends_result.scalars().all()
    
    friend_ids = []
    for f in friendships:
        friend_ids.append(f.addressee_id if f.requester_id == current_user.id else f.requester_id)
    
    if friend_ids:
        # Get goals from friends with 'friends' privacy setting
        friend_goals_stmt = select(models.Goal).where(
            models.Goal.user_id.in_(friend_ids),
            models.Goal.privacy_setting == models.GoalPrivacy.friends
        )
        friend_goals_result = await db.execute(friend_goals_stmt)
        friend_goals = friend_goals_result.scalars().all()
        friend_goal_ids = [g.id for g in friend_goals]
        
        if friend_goal_ids:
            requests_stmt = select(models.IntervalChangeRequest).where(
                models.IntervalChangeRequest.goal_id.in_(friend_goal_ids),
                models.IntervalChangeRequest.status == "pending"
            )
            requests_result = await db.execute(requests_stmt)
            requests = requests_result.scalars().all()
            
            for req in requests:
                # Skip if already added
                if any(p.id == req.id for p in pending_requests):
                    continue
                    
                goal = next((g for g in friend_goals if g.id == req.goal_id), None)
                
                user_stmt = select(models.User).where(models.User.id == req.requester_id)
                user_result = await db.execute(user_stmt)
                user = user_result.scalars().first()
                
                if goal and user:
                    pending_requests.append(schemas.IntervalChangeRequestOut(
                        id=req.id,
                        goal_id=req.goal_id,
                        goal_title=goal.title,
                        requester_id=req.requester_id,
                        requester_name=user.username,
                        current_interval=req.current_interval,
                        requested_interval=req.requested_interval,
                        status=req.status,
                        created_at=req.created_at
                    ))
    
    return pending_requests


@router.post("/{request_id}/verify")
async def verify_interval_change_request(
    request_id: UUID,
    verification: schemas.IntervalChangeRequestVerify,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    Approve or reject an interval change request.
    If approved, updates the goal's milestone_interval_days.
    """
    # 1. Get the request
    request_stmt = select(models.IntervalChangeRequest).where(
        models.IntervalChangeRequest.id == request_id
    )
    result = await db.execute(request_stmt)
    change_request = result.scalars().first()
    
    if not change_request:
        raise HTTPException(status_code=404, detail="Interval change request not found")
    
    if change_request.status != "pending":
        raise HTTPException(status_code=400, detail="This request has already been resolved")
    
    # 2. Verify the user has permission to verify this request
    goal_stmt = select(models.Goal).where(models.Goal.id == change_request.goal_id)
    goal_result = await db.execute(goal_stmt)
    goal = goal_result.scalars().first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    # Check permission based on privacy setting
    has_permission = False
    
    if goal.privacy_setting == models.GoalPrivacy.select_friends:
        viewer_stmt = select(models.GoalAllowedViewer).where(
            models.GoalAllowedViewer.goal_id == goal.id,
            models.GoalAllowedViewer.user_id == current_user.id,
            models.GoalAllowedViewer.can_verify == True
        )
        viewer_result = await db.execute(viewer_stmt)
        has_permission = viewer_result.scalars().first() is not None
    
    elif goal.privacy_setting == models.GoalPrivacy.friends:
        friend_stmt = select(models.Friend).where(
            or_(
                and_(
                    models.Friend.requester_id == current_user.id,
                    models.Friend.addressee_id == goal.user_id,
                    models.Friend.status == models.FriendStatus.accepted
                ),
                and_(
                    models.Friend.requester_id == goal.user_id,
                    models.Friend.addressee_id == current_user.id,
                    models.Friend.status == models.FriendStatus.accepted
                )
            )
        )
        friend_result = await db.execute(friend_stmt)
        has_permission = friend_result.scalars().first() is not None
    
    if not has_permission:
        raise HTTPException(status_code=403, detail="You don't have permission to verify this request")
    
    # 3. Update the request status
    change_request.status = "approved" if verification.approved else "rejected"
    change_request.resolved_at = datetime.now(timezone.utc)
    change_request.resolved_by = current_user.id
    
    # 4. If approved, update the goal's milestone_interval_days
    if verification.approved:
        goal.milestone_interval_days = change_request.requested_interval
    
    # 5. Notify the requester
    status_text = "approved" if verification.approved else "rejected"
    await create_notification(
        db,
        recipient_id=change_request.requester_id,
        type=models.NotificationType.interval_change_request,
        message=f"{current_user.username} {status_text} your interval change request for '{goal.title}'",
        actor_id=current_user.id,
        goal_id=goal.id
    )
    
    await db.commit()
    
    return {
        "message": f"Interval change request {status_text}",
        "status": change_request.status,
        "new_interval": goal.milestone_interval_days if verification.approved else None
    }
