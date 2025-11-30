from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from uuid import UUID

from app.api import deps
from app.db import models
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

router = APIRouter()


class NotificationOut(BaseModel):
    id: str
    recipient_id: str
    actor_id: Optional[str]
    type: str
    goal_id: Optional[str]
    proof_id: Optional[str]
    message: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class NotificationUpdateStatus(BaseModel):
    status: str  # 'read' or 'archived'


@router.get("/notifications", response_model=List[NotificationOut])
async def list_notifications(
    status: Optional[str] = None,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    List notifications for the current user.
    Optional status filter: 'unread', 'read', 'archived'
    """
    # Build query
    query = select(models.PartnerNotification).where(
        models.PartnerNotification.recipient_id == current_user.id
    )
    
    # Apply status filter if provided
    if status:
        if status == 'unread':
            query = query.where(
                models.PartnerNotification.status == models.NotificationState.unread
            )
        elif status == 'read':
            query = query.where(
                models.PartnerNotification.status == models.NotificationState.read
            )
        elif status == 'archived':
            query = query.where(
                models.PartnerNotification.status == models.NotificationState.archived
            )
    
    # Order by newest first
    query = query.order_by(models.PartnerNotification.created_at.desc())
    
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    return notifications


@router.patch("/notifications/{notification_id}", response_model=NotificationOut)
async def update_notification(
    notification_id: UUID,
    update_data: NotificationUpdateStatus,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    Update a notification's status (mark as read, archived, etc.)
    """
    # Find the notification
    query = select(models.PartnerNotification).where(
        models.PartnerNotification.id == notification_id,
        models.PartnerNotification.recipient_id == current_user.id
    )
    result = await db.execute(query)
    notification = result.scalars().first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    # Update status
    if update_data.status == 'read':
        notification.status = models.NotificationState.read
    elif update_data.status == 'archived':
        notification.status = models.NotificationState.archived
    elif update_data.status == 'unread':
        notification.status = models.NotificationState.unread
    else:
        raise HTTPException(status_code=400, detail="Invalid status value")
    
    await db.commit()
    await db.refresh(notification)
    
    return notification


@router.patch("/notifications/{notification_id}/read", response_model=NotificationOut)
async def mark_notification_as_read(
    notification_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    Mark a specific notification as read.
    """
    return await update_notification(
        notification_id,
        NotificationUpdateStatus(status='read'),
        db,
        current_user
    )


@router.post("/notifications/{notification_id}/archive", response_model=NotificationOut)
async def archive_notification(
    notification_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    Archive a notification.
    """
    return await update_notification(
        notification_id,
        NotificationUpdateStatus(status='archived'),
        db,
        current_user
    )


@router.post("/notifications/mark-all-read")
async def mark_all_notifications_as_read(
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    Mark all unread notifications as read for the current user.
    """
    query = select(models.PartnerNotification).where(
        models.PartnerNotification.recipient_id == current_user.id,
        models.PartnerNotification.status == models.NotificationState.unread
    )
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    for notification in notifications:
        notification.status = models.NotificationState.read
    
    await db.commit()
    
    return {"message": f"Marked {len(notifications)} notifications as read"}


@router.get("/notifications/unread-count")
async def get_unread_notification_count(
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    Get the count of unread notifications for the current user.
    """
    query = select(models.PartnerNotification).where(
        models.PartnerNotification.recipient_id == current_user.id,
        models.PartnerNotification.status == models.NotificationState.unread
    )
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    return {"unread_count": len(notifications)}