from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import PartnerNotification, NotificationType, NotificationState
from uuid import UUID

async def create_notification(
    db: AsyncSession,
    recipient_id: UUID,
    type: NotificationType,
    message: str,
    actor_id: UUID = None,
    goal_id: UUID = None,
    proof_id: UUID = None,
):
    notif = PartnerNotification(
        recipient_id=recipient_id,
        actor_id=actor_id,
        type=type,
        message=message,
        goal_id=goal_id,
        proof_id=proof_id,
        status=NotificationState.unread
    )
    db.add(notif)
    await db.commit()