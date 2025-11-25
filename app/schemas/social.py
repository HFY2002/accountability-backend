from pydantic import BaseModel
from uuid import UUID
from app.db.models import FriendStatus
from datetime import datetime
from typing import Optional

class FriendRequestCreateIn(BaseModel):
    target_user_id: UUID

class FriendOut(BaseModel):
    id: UUID
    user_id: UUID  # The other user's ID (not the current user)
    name: str  # Other user's username
    email: str  # Other user's email
    avatar: Optional[str] = None  # Other user's avatar URL
    status: str  # 'accepted', 'pending_sent', 'pending_received'
    added_at: datetime

    class Config:
        from_attributes = True