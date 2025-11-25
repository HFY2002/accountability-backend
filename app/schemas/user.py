from pydantic import BaseModel, EmailStr
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str


class UserOut(BaseModel):
    id: UUID
    email: str
    username: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserProfileOut(BaseModel):
    id: UUID
    user_id: UUID
    avatar_url: Optional[str]
    bio: Optional[str]
    onboarding_completed: bool

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    avatar_url: Optional[str] = None
    bio: Optional[str] = None


class UserInterestsUpdate(BaseModel):
    category_names: List[str]


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict
