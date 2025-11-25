from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from app.api import deps
from app.schemas import social as schemas
from app.db import models
from app.services.notification import create_notification
from uuid import UUID

router = APIRouter()

@router.get("", response_model=list[schemas.FriendOut])
async def list_friends(
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    List all friends and friend requests for the current user.
    Returns both accepted friends and pending requests (both sent and received).
    """
    # Get all friend relationships where current user is either requester or addressee
    stmt = select(models.Friend).where(
        or_(
            models.Friend.requester_id == current_user.id,
            models.Friend.addressee_id == current_user.id
        )
    )
    result = await db.execute(stmt)
    friendships = result.scalars().all()
    
    # Transform the friendships into FriendOut schema format
    friends_list = []
    for friendship in friendships:
        # Determine the other user's ID and the friendship status from current user's perspective
        if friendship.requester_id == current_user.id:
            # Current user sent the request
            other_user_id = friendship.addressee_id
            if friendship.status == models.FriendStatus.pending:
                # Current user is waiting for their request to be accepted
                status = "pending_sent"
            else:
                status = "accepted"
        else:
            # Current user received the request
            other_user_id = friendship.requester_id
            if friendship.status == models.FriendStatus.pending:
                # Current user needs to accept/reject this request
                status = "pending_received"
            else:
                status = "accepted"
        
        # Get the other user's details
        user_stmt = select(models.User).where(models.User.id == other_user_id)
        user_result = await db.execute(user_stmt)
        other_user = user_result.scalars().first()
        
        if other_user:
            friends_list.append(schemas.FriendOut(
                id=str(friendship.id),
                user_id=str(other_user.id),
                name=other_user.username,
                email=other_user.email,
                avatar="",  # Add avatar URL if available in User model
                status=status,
                added_at=friendship.created_at
            ))
    
    return friends_list

@router.post("/requests", response_model=schemas.FriendOut)
async def send_friend_request(
    request_in: schemas.FriendRequestCreateIn,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    target_id = request_in.target_user_id
    
    # Check for existing reverse request (UX requirement)
    stmt = select(models.Friend).where(
        models.Friend.requester_id == target_id,
        models.Friend.addressee_id == current_user.id,
        models.Friend.status == models.FriendStatus.pending
    )
    result = await db.execute(stmt)
    reverse_request = result.scalars().first()

    if reverse_request:
        # Auto-accept
        reverse_request.status = models.FriendStatus.accepted
        await db.commit()
        await db.refresh(reverse_request)
        
        await create_notification(
            db, recipient_id=target_id, 
            type=models.NotificationType.friend_request_accepted,
            message=f"{current_user.username} accepted your friend request",
            actor_id=current_user.id
        )
        return reverse_request

    # Create new request
    new_friendship = models.Friend(
        requester_id=current_user.id,
        addressee_id=target_id,
        status=models.FriendStatus.pending
    )
    db.add(new_friendship)
    await db.commit()
    
    await create_notification(
        db, recipient_id=target_id,
        type=models.NotificationType.friend_request,
        message=f"{current_user.username} sent you a friend request",
        actor_id=current_user.id
    )
    
    return new_friendship