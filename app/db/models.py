from __future__ import annotations
import uuid
import enum
from sqlalchemy import (
    Column, String, Boolean, ForeignKey, Integer, Text, Date, DateTime, 
    Enum, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# --- Enums ---
class FriendStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    blocked = "blocked"

class GoalStatus(str, enum.Enum):
    active = "active"
    failed = "failed"
    completed_pending = "completed-pending-verification"
    completed_verified = "completed-verified"
    archived = "archived"

class GoalPrivacy(str, enum.Enum):
    private = "private"
    friends = "friends"
    select_friends = "select_friends"

class MilestoneType(str, enum.Enum):
    flexible = "flexible"
    defined = "defined"

class ProofStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"  # NEW: Added expired status for proofs past verification window

class NotificationType(str, enum.Enum):
    friend_request = "friend_request"
    friend_request_accepted = "friend_request_accepted"
    proof_submission = "proof_submission"
    proof_verified = "proof_verified"
    proof_expired = "proof_expired"  # NEW: Notification for expired proofs
    goal_completion_request = "goal_completion_request"
    goal_completed = "goal_completed"
    interval_change_request = "interval_change_request"

class NotificationState(str, enum.Enum):
    unread = "unread"
    read = "read"
    archived = "archived"

# --- Tables ---

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=True)
    auth_provider = Column(String, default="local", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    profile = relationship("UserProfile", back_populates="user", uselist=False)
    goals = relationship("Goal", back_populates="owner")
    
    # Note: Friends query usually requires custom join or helper methods

class UserProfile(Base):
    __tablename__ = "user_profiles"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    avatar_url = Column(String)
    bio = Column(Text)
    onboarding_completed = Column(Boolean, default=False, nullable=False)
    
    user = relationship("User", back_populates="profile")

class GoalCategory(Base):
    __tablename__ = "goal_categories"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    emoji = Column(String)
    is_default = Column(Boolean, default=False)

class Goal(Base):
    __tablename__ = "goals"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("goal_categories.id"))
    title = Column(String, nullable=False)
    description = Column(Text)
    
    milestone_type = Column(Enum(MilestoneType), nullable=False)
    milestone_interval_days = Column(Integer)
    milestone_quantity = Column(Integer)
    milestone_unit = Column(String)
    
    start_date = Column(Date, nullable=False)
    deadline = Column(Date, nullable=False)
    privacy_setting = Column(Enum(GoalPrivacy), default=GoalPrivacy.private)
    
    image_url = Column(String)
    user_story = Column(Text)
    status = Column(Enum(GoalStatus), default=GoalStatus.active)
    
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="goals")
    milestones = relationship("Milestone", back_populates="goal", order_by="Milestone.order_index")
    proofs = relationship("Proof", back_populates="goal")
    allowed_viewers = relationship("GoalAllowedViewer", back_populates="goal")

class GoalAllowedViewer(Base):
    __tablename__ = "goal_allowed_viewers"
    goal_id = Column(UUID(as_uuid=True), ForeignKey("goals.id"), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    can_verify = Column(Boolean, default=True)
    
    goal = relationship("Goal", back_populates="allowed_viewers")
    user = relationship("User") 

class Milestone(Base):
    __tablename__ = "milestones"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    goal_id = Column(UUID(as_uuid=True), ForeignKey("goals.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    
    is_flexible = Column(Boolean, default=False)
    batch_number = Column(Integer, default=1)
    order_index = Column(Integer, nullable=False)
    due_date = Column(Date)
    
    completed = Column(Boolean, default=False)
    progress = Column(Integer, default=0)
    completed_at = Column(DateTime(timezone=True))
    
    goal = relationship("Goal", back_populates="milestones")
    proofs = relationship("Proof", back_populates="milestone")

class Proof(Base):
    __tablename__ = "proofs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    goal_id = Column(UUID(as_uuid=True), ForeignKey("goals.id"), nullable=False)
    milestone_id = Column(UUID(as_uuid=True), ForeignKey("milestones.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    image_url = Column(String, nullable=False)
    caption = Column(Text)
    status = Column(Enum(ProofStatus), default=ProofStatus.pending)
    required_verifications = Column(Integer, default=1)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    verification_expires_at = Column(DateTime(timezone=True))  # NEW: 72 hour expiry
    
    goal = relationship("Goal", back_populates="proofs")
    milestone = relationship("Milestone", back_populates="proofs")
    verifications = relationship("ProofVerification", back_populates="proof")
    uploader = relationship("User")

class ProofVerification(Base):
    __tablename__ = "proof_verifications"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proof_id = Column(UUID(as_uuid=True), ForeignKey("proofs.id"), nullable=False)
    verifier_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    approved = Column(Boolean, nullable=False)
    comment = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    proof = relationship("Proof", back_populates="verifications")
    verifier = relationship("User")

class Friend(Base):
    __tablename__ = "friends"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requester_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    addressee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status = Column(Enum(FriendStatus), default=FriendStatus.pending)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class PartnerNotification(Base):
    __tablename__ = "partner_notifications"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    type = Column(Enum(NotificationType), nullable=False)
    
    goal_id = Column(UUID(as_uuid=True), ForeignKey("goals.id"))
    proof_id = Column(UUID(as_uuid=True), ForeignKey("proofs.id"))
    
    message = Column(Text, nullable=False)
    status = Column(Enum(NotificationState), default=NotificationState.unread)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class DailyTask(Base):
    __tablename__ = "daily_tasks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    goal_id = Column(UUID(as_uuid=True), ForeignKey("goals.id"), nullable=True)
    title = Column(String, nullable=False)
    completed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class GoalTemplate(Base):
    __tablename__ = "goal_templates"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    description = Column(Text)
    category_id = Column(Integer, ForeignKey("goal_categories.id"), nullable=False)
    image_url = Column(String)
    milestones = Column(Text)  # JSON string array of milestone titles
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    category = relationship("GoalCategory")

class Quote(Base):
    __tablename__ = "quotes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    text = Column(Text, nullable=False)
    author = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())