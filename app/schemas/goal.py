from pydantic import BaseModel, validator
from typing import List, Optional, Literal
from datetime import date, datetime
from uuid import UUID
from app.db.models import GoalStatus, GoalPrivacy, MilestoneType
from .common import UserSummaryOut


class MilestoneCreateIn(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[date] = None
    order_index: int
    batch_number: Optional[int] = None
    is_flexible: bool = False


class MilestoneAppendIn(BaseModel):
    title: str
    description: Optional[str] = None


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
    failed: bool = False  # NEW FIELD
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
    selected_friend_ids: Optional[List[UUID]] = None


class GoalGiveUpIn(BaseModel):
    failure_reason: str


class GoalCreateFlexibleIn(GoalBaseIn):
    milestone_type: Literal["flexible"] = "flexible"
    milestone_interval_days: int
    initial_milestones: List[MilestoneCreateIn]
    selected_friend_ids: Optional[List[UUID]] = None


class GoalCreateDefinedIn(GoalBaseIn):
    milestone_type: Literal["defined"] = "defined"
    milestone_interval_days: int
    milestone_quantity: int
    milestone_unit: str
    selected_friend_ids: Optional[List[UUID]] = None


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
    failure_reason: Optional[str] = None
    milestones: List[MilestoneOut] = []  # NEW: Include milestones
    recent_milestones: Optional[str] = None  # NEW: Computed field for display

    class Config:
        from_attributes = True
    
    @validator('recent_milestones', always=True)
    def compute_recent_milestones(cls, v, values):
        """Compute recent_milestones from the milestones list"""
        milestones = values.get('milestones', [])
        if not milestones:
            return ""
        
        # Sort milestones by order_index
        sorted_milestones = sorted(milestones, key=lambda m: m.order_index)
        
        # Get completed milestones (excluding failed ones)
        completed = [m for m in sorted_milestones if m.completed and not m.failed]
        
        # Get incomplete milestones (not completed and not failed)
        incomplete = [m for m in sorted_milestones if not m.completed and not m.failed]
        
        # Select last 2 completed
        last_two_completed = completed[-2:] if len(completed) >= 2 else completed
        
        # Select first incomplete (most recent one to work on)
        first_incomplete = incomplete[0:1] if incomplete else []
        
        # Combine them
        display_milestones = last_two_completed + first_incomplete
        
        # Return comma-separated titles
        return ", ".join([m.title for m in display_milestones])


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
    failure_reason: Optional[str] = None
    verifying_partners: Optional[List[UserSummaryOut]] = None

    class Config:
        from_attributes = True
