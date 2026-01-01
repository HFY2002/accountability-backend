from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime

class IntervalChangeRequestCreate(BaseModel):
    goal_id: UUID
    requested_interval: int

class IntervalChangeRequestOut(BaseModel):
    id: UUID
    goal_id: UUID
    goal_title: str  # For display in verification queue
    requester_id: UUID
    requester_name: str  # For display
    current_interval: int
    requested_interval: int
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[UUID] = None

    class Config:
        from_attributes = True

class IntervalChangeRequestVerify(BaseModel):
    approved: bool
    comment: Optional[str] = None
