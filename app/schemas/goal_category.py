from pydantic import BaseModel
from typing import Optional


class GoalCategoryOut(BaseModel):
    id: int
    name: str
    slug: str
    emoji: Optional[str] = None
    is_default: bool

    class Config:
        from_attributes = True
