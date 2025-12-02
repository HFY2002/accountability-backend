from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class UserSummaryOut(BaseModel):
    id: UUID
    username: str
    email: str
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True