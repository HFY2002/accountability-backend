from pydantic import BaseModel
from typing import Optional
from uuid import UUID


class DailyTaskCreate(BaseModel):
    goal_id: Optional[UUID] = None
    title: str


class DailyTaskOut(BaseModel):
    id: UUID
    user_id: UUID
    goal_id: Optional[UUID]
    title: str
    completed: bool

    class Config:
        from_attributes = True
