from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.db.models import ProofStatus
from .common import UserSummaryOut
from typing import Any

class ProofCreateIn(BaseModel):
    goal_id: UUID
    milestone_id: Optional[UUID] = None
    caption: Optional[str] = None
    storage_key: str  # Uploaded file key from MinIO

class ProofVerificationCreateIn(BaseModel):
    approved: bool
    comment: Optional[str] = None

class ProofVerificationOut(BaseModel):
    id: UUID
    verifier_id: UUID
    verifierName: Optional[str] = None  # Added for frontend compatibility
    approved: bool
    comment: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ProofOut(BaseModel):
    id: UUID
    goal_id: UUID
    milestone_id: Optional[UUID] = None
    user_id: UUID
    userName: Optional[str] = None  # Added for frontend compatibility
    image_url: str
    caption: Optional[str] = None
    status: ProofStatus
    requiredVerifications: int = 1  # Added for frontend compatibility
    uploadedAt: Optional[datetime] = None  # Added for frontend compatibility
    verifications: List[ProofVerificationOut] = []
    goalTitle: Optional[str] = None  # Added for frontend compatibility

    class Config:
        from_attributes = True