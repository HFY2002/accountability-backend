from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from uuid import UUID


class GoalTemplateOut(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    milestones: List[str]
    created_at: datetime

    class Config:
        from_attributes = True


class GoalTemplateIn(BaseModel):
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    milestones: List[str]
