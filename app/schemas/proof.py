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
    verifier_name: Optional[str] = None  # Renamed from verifierName
    approved: bool
    comment: Optional[str] = None
    timestamp: datetime  # Renamed from created_at

    class Config:
        from_attributes = True

class ProofOut(BaseModel):
    id: UUID
    goal_id: UUID
    milestone_id: Optional[UUID] = None
    user_id: UUID
    user_name: Optional[str] = None  # Renamed from userName
    image_url: str
    caption: Optional[str] = None
    status: ProofStatus
    requiredVerifications: int = 1  # Added for frontend compatibility
    uploadedAt: Optional[datetime] = None  # Maps to uploaded_at in DB
    verificationExpiresAt: Optional[datetime] = None  # NEW: 72 hour expiry time
    verifications: List[ProofVerificationOut] = []
    goalTitle: Optional[str] = None  # Added for frontend compatibility
    milestoneTitle: Optional[str] = None  # Milestone title for frontend
    milestoneDescription: Optional[str] = None  # Milestone description for frontend
    canVerify: Optional[bool] = None  # NEW: Whether current user can verify this proof

    class Config:
        from_attributes = True