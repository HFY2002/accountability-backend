from pydantic import BaseModel
from typing import List, Optional, Literal
from datetime import date, datetime
from uuid import UUID
from app.db.models import GoalStatus, GoalPrivacy, MilestoneType
from .common import UserSummaryOut

# Input schemas needed for complete API

class MilestoneCreateIn(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[date] = None
    order_index: int
    batch_number: Optional[int] = None
    is_flexible: bool = False


class MilestoneBatchCreate(BaseModel):
    start_date: date
    milestones: List[MilestoneCreateIn]


class MilestoneOut(BaseModel):
    id: UUID
    goal_id: UUID
    title: str
    description: Optional[str] = None
    batch_number: int
    is_flexible: bool
    order_index: int
    due_date: Optional[date] = None
    completed: bool
    progress: int
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GoalBaseIn(BaseModel):
    title: str
    description: Optional[str] = None
    start_date: date
    deadline: date
    privacy_setting: GoalPrivacy = GoalPrivacy.private
    image_url: Optional[str] = None
    user_story: Optional[str] = None


class GoalUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    privacy_setting: Optional[GoalPrivacy] = None
    image_url: Optional[str] = None


class GoalCreateFlexibleIn(GoalBaseIn):
    milestone_type: Literal["flexible"] = "flexible"
    milestone_interval_days: int
    initial_milestones: List[MilestoneCreateIn]


class GoalCreateDefinedIn(GoalBaseIn):
    milestone_type: Literal["defined"] = "defined"
    milestone_interval_days: int
    milestone_quantity: int
    milestone_unit: str


class GoalListOut(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    description: Optional[str]
    milestone_type: MilestoneType
    milestone_interval_days: Optional[int]
    start_date: date
    deadline: date
    privacy_setting: GoalPrivacy
    image_url: Optional[str]
    status: GoalStatus
    is_completed: bool
    milestone_quantity: Optional[int]
    milestone_unit: Optional[str]

    class Config:
        from_attributes = True


class GoalDetailOut(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    description: Optional[str] = None
    milestone_type: MilestoneType
    status: GoalStatus
    is_completed: bool
    milestones: List[MilestoneOut]
    start_date: date
    deadline: date
    privacy_setting: GoalPrivacy
    image_url: Optional[str] = None
    milestone_quantity: Optional[int] = None
    milestone_unit: Optional[str] = None
    user_story: Optional[str] = None

    class Config:
        from_attributes = True
