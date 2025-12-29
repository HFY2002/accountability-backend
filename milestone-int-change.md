# Implementation Plan: Check-in Interval Change Request Approval Flow

## Problem Summary

When a user with a non-private goal that has accountability partners clicks "Change" next to "Check-in Interval", selects a new interval, and clicks "Request Approval", **nothing is actually sent to the accountability partner**. The current implementation only shows a toast notification (fake success message) but does not make any backend API call.

**Root Cause**: The `handleIntervalChangeRequest` function in `/root/frontend/src/components/goals/GoalDetailView.tsx` (lines 152-161) only displays a toast message without making any API call to the backend.

**Current broken code (lines 152-161 in GoalDetailView.tsx)**:
```typescript
const handleIntervalChangeRequest = () => {
  if (!newInterval) {
    toast.error('Please select an interval first');
    return;
  }
  toast.success(`Interval change request sent to ${(goal.verifying_partners && goal.verifying_partners.length > 0 ? goal.verifying_partners[0].username : 'your goal buddies')} for approval!`, {
    description: 'They will need to approve before the change takes effect.',
  });
  setIntervalChangeOpen(false);
};
```

## Required Behavior

1. When a user requests an interval change, a **pending interval change request** should be created
2. This request should appear in the accountability partner's **Verification Queue** under "Friends' Pending Section"
3. When the partner approves the request, the goal's `milestone_interval_days` should be updated to the new value
4. This follows the same approval flow as milestone proof requests

---

## Proposed Changes

### Component 1: Backend - New Database Model for Interval Change Requests

We need a new table to persist interval change requests with their status.

#### [NEW] `/root/backend/app/db/interval_change_request.py`

Create a new model to track interval change requests:

```python
# This will be added to /root/backend/app/db/models.py instead of a separate file
# Add the following class after the existing models

class IntervalChangeRequest(Base):
    __tablename__ = "interval_change_requests"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    goal_id = Column(UUID(as_uuid=True), ForeignKey("goals.id"), nullable=False)
    requester_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    current_interval = Column(Integer, nullable=False)
    requested_interval = Column(Integer, nullable=False)
    status = Column(String, default="pending")  # pending, approved, rejected
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    goal = relationship("Goal")
    requester = relationship("User", foreign_keys=[requester_id])
    resolver = relationship("User", foreign_keys=[resolved_by])
```

---

#### [MODIFY] `/root/backend/app/db/models.py`

Add the `IntervalChangeRequest` model class after the existing models (around line 200, before the `Quote` class).

**Add this import at the top if needed**: The file already has the necessary imports.

**Add the IntervalChangeRequest class** (see code above).

---

### Component 2: Backend - Database Migration

#### [NEW] `/root/backend/app/alembic/versions/[timestamp]_add_interval_change_requests.py`

Create a new Alembic migration to add the `interval_change_requests` table:

```python
"""add interval change requests table

Revision ID: [auto-generated]
Revises: [previous revision]
Create Date: [auto-generated]
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '[auto-generated]'
down_revision = '[previous revision - check existing migrations]'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'interval_change_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('goal_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('goals.id'), nullable=False),
        sa.Column('requester_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('current_interval', sa.Integer(), nullable=False),
        sa.Column('requested_interval', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
    )

def downgrade() -> None:
    op.drop_table('interval_change_requests')
```

**After creating the migration**, run:
```bash
cd /root/backend
alembic upgrade head
```

---

### Component 3: Backend - Schema Definitions

#### [NEW] `/root/backend/app/schemas/interval_change.py`

Create a new schema file for interval change request data:

```python
from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime

class IntervalChangeRequestCreate(BaseModel):
    goal_id: UUID
    requested_interval: int

class IntervalChangeRequestOut(BaseModel):
    id: UUID
    goal_id: UUID
    goal_title: str  # For display in verification queue
    requester_id: UUID
    requester_name: str  # For display
    current_interval: int
    requested_interval: int
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[UUID] = None

    class Config:
        from_attributes = True

class IntervalChangeRequestVerify(BaseModel):
    approved: bool
    comment: Optional[str] = None
```

---

### Component 4: Backend - API Endpoint

#### [NEW] `/root/backend/app/api/interval_changes.py`

Create a new API file with endpoints for interval change requests:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from uuid import UUID
from datetime import datetime, timezone

from app.api import deps
from app.schemas import interval_change as schemas
from app.db import models
from app.services.notification import create_notification

router = APIRouter()

@router.post("", response_model=schemas.IntervalChangeRequestOut)
async def create_interval_change_request(
    request_in: schemas.IntervalChangeRequestCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    Create an interval change request for a goal.
    Sends notifications to all accountability partners.
    """
    # 1. Validate goal exists and belongs to current user
    goal_stmt = select(models.Goal).where(
        models.Goal.id == request_in.goal_id,
        models.Goal.user_id == current_user.id
    )
    result = await db.execute(goal_stmt)
    goal = result.scalars().first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    # 2. Check goal is not private
    if goal.privacy_setting == models.GoalPrivacy.private:
        raise HTTPException(status_code=400, detail="Cannot request interval change for private goals")
    
    # 3. Check for existing pending request
    existing_stmt = select(models.IntervalChangeRequest).where(
        models.IntervalChangeRequest.goal_id == request_in.goal_id,
        models.IntervalChangeRequest.status == "pending"
    )
    existing_result = await db.execute(existing_stmt)
    if existing_result.scalars().first():
        raise HTTPException(status_code=400, detail="There is already a pending interval change request for this goal")
    
    # 4. Create the interval change request
    db_request = models.IntervalChangeRequest(
        goal_id=request_in.goal_id,
        requester_id=current_user.id,
        current_interval=goal.milestone_interval_days or 0,
        requested_interval=request_in.requested_interval,
        status="pending"
    )
    db.add(db_request)
    await db.flush()
    
    # 5. Send notifications to accountability partners
    if goal.privacy_setting == models.GoalPrivacy.select_friends:
        # Get allowed viewers
        viewers_stmt = select(models.GoalAllowedViewer).where(
            models.GoalAllowedViewer.goal_id == goal.id,
            models.GoalAllowedViewer.can_verify == True
        )
        viewers_result = await db.execute(viewers_stmt)
        viewers = viewers_result.scalars().all()
        
        for viewer in viewers:
            await create_notification(
                db,
                recipient_id=viewer.user_id,
                type=models.NotificationType.interval_change_request,
                message=f"{current_user.username} requested to change check-in interval for '{goal.title}' from {goal.milestone_interval_days or 0} to {request_in.requested_interval} days",
                actor_id=current_user.id,
                goal_id=goal.id
            )
    
    elif goal.privacy_setting == models.GoalPrivacy.friends:
        # Get all friends
        friends_stmt = select(models.Friend).where(
            or_(
                models.Friend.requester_id == current_user.id,
                models.Friend.addressee_id == current_user.id
            ),
            models.Friend.status == models.FriendStatus.accepted
        )
        friends_result = await db.execute(friends_stmt)
        friendships = friends_result.scalars().all()
        
        for friendship in friendships:
            friend_id = (friendship.addressee_id if friendship.requester_id == current_user.id 
                        else friendship.requester_id)
            
            await create_notification(
                db,
                recipient_id=friend_id,
                type=models.NotificationType.interval_change_request,
                message=f"{current_user.username} requested to change check-in interval for '{goal.title}' from {goal.milestone_interval_days or 0} to {request_in.requested_interval} days",
                actor_id=current_user.id,
                goal_id=goal.id
            )
    
    await db.commit()
    await db.refresh(db_request)
    
    return schemas.IntervalChangeRequestOut(
        id=db_request.id,
        goal_id=db_request.goal_id,
        goal_title=goal.title,
        requester_id=db_request.requester_id,
        requester_name=current_user.username,
        current_interval=db_request.current_interval,
        requested_interval=db_request.requested_interval,
        status=db_request.status,
        created_at=db_request.created_at
    )


@router.get("/pending", response_model=list[schemas.IntervalChangeRequestOut])
async def list_pending_interval_change_requests(
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    List all pending interval change requests that the current user can verify.
    These are requests from friends' goals where the user is an accountability partner.
    """
    pending_requests = []
    
    # Get requests from goals where current user is an allowed viewer
    viewer_goals_stmt = select(models.GoalAllowedViewer.goal_id).where(
        models.GoalAllowedViewer.user_id == current_user.id,
        models.GoalAllowedViewer.can_verify == True
    )
    viewer_goals_result = await db.execute(viewer_goals_stmt)
    viewer_goal_ids = [row[0] for row in viewer_goals_result.fetchall()]
    
    # Get pending requests for those goals
    if viewer_goal_ids:
        requests_stmt = select(models.IntervalChangeRequest).where(
            models.IntervalChangeRequest.goal_id.in_(viewer_goal_ids),
            models.IntervalChangeRequest.status == "pending"
        )
        requests_result = await db.execute(requests_stmt)
        requests = requests_result.scalars().all()
        
        for req in requests:
            # Get goal and requester details
            goal_stmt = select(models.Goal).where(models.Goal.id == req.goal_id)
            goal_result = await db.execute(goal_stmt)
            goal = goal_result.scalars().first()
            
            user_stmt = select(models.User).where(models.User.id == req.requester_id)
            user_result = await db.execute(user_stmt)
            user = user_result.scalars().first()
            
            if goal and user:
                pending_requests.append(schemas.IntervalChangeRequestOut(
                    id=req.id,
                    goal_id=req.goal_id,
                    goal_title=goal.title,
                    requester_id=req.requester_id,
                    requester_name=user.username,
                    current_interval=req.current_interval,
                    requested_interval=req.requested_interval,
                    status=req.status,
                    created_at=req.created_at
                ))
    
    # Also check for friends privacy goals
    friends_stmt = select(models.Friend).where(
        or_(
            models.Friend.requester_id == current_user.id,
            models.Friend.addressee_id == current_user.id
        ),
        models.Friend.status == models.FriendStatus.accepted
    )
    friends_result = await db.execute(friends_stmt)
    friendships = friends_result.scalars().all()
    
    friend_ids = []
    for f in friendships:
        friend_ids.append(f.addressee_id if f.requester_id == current_user.id else f.requester_id)
    
    if friend_ids:
        # Get goals from friends with 'friends' privacy setting
        friend_goals_stmt = select(models.Goal).where(
            models.Goal.user_id.in_(friend_ids),
            models.Goal.privacy_setting == models.GoalPrivacy.friends
        )
        friend_goals_result = await db.execute(friend_goals_stmt)
        friend_goals = friend_goals_result.scalars().all()
        friend_goal_ids = [g.id for g in friend_goals]
        
        if friend_goal_ids:
            requests_stmt = select(models.IntervalChangeRequest).where(
                models.IntervalChangeRequest.goal_id.in_(friend_goal_ids),
                models.IntervalChangeRequest.status == "pending"
            )
            requests_result = await db.execute(requests_stmt)
            requests = requests_result.scalars().all()
            
            for req in requests:
                # Skip if already added
                if any(p.id == req.id for p in pending_requests):
                    continue
                    
                goal = next((g for g in friend_goals if g.id == req.goal_id), None)
                
                user_stmt = select(models.User).where(models.User.id == req.requester_id)
                user_result = await db.execute(user_stmt)
                user = user_result.scalars().first()
                
                if goal and user:
                    pending_requests.append(schemas.IntervalChangeRequestOut(
                        id=req.id,
                        goal_id=req.goal_id,
                        goal_title=goal.title,
                        requester_id=req.requester_id,
                        requester_name=user.username,
                        current_interval=req.current_interval,
                        requested_interval=req.requested_interval,
                        status=req.status,
                        created_at=req.created_at
                    ))
    
    return pending_requests


@router.post("/{request_id}/verify")
async def verify_interval_change_request(
    request_id: UUID,
    verification: schemas.IntervalChangeRequestVerify,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    Approve or reject an interval change request.
    If approved, updates the goal's milestone_interval_days.
    """
    # 1. Get the request
    request_stmt = select(models.IntervalChangeRequest).where(
        models.IntervalChangeRequest.id == request_id
    )
    result = await db.execute(request_stmt)
    change_request = result.scalars().first()
    
    if not change_request:
        raise HTTPException(status_code=404, detail="Interval change request not found")
    
    if change_request.status != "pending":
        raise HTTPException(status_code=400, detail="This request has already been resolved")
    
    # 2. Verify the user has permission to verify this request
    goal_stmt = select(models.Goal).where(models.Goal.id == change_request.goal_id)
    goal_result = await db.execute(goal_stmt)
    goal = goal_result.scalars().first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    # Check permission based on privacy setting
    has_permission = False
    
    if goal.privacy_setting == models.GoalPrivacy.select_friends:
        viewer_stmt = select(models.GoalAllowedViewer).where(
            models.GoalAllowedViewer.goal_id == goal.id,
            models.GoalAllowedViewer.user_id == current_user.id,
            models.GoalAllowedViewer.can_verify == True
        )
        viewer_result = await db.execute(viewer_stmt)
        has_permission = viewer_result.scalars().first() is not None
    
    elif goal.privacy_setting == models.GoalPrivacy.friends:
        friend_stmt = select(models.Friend).where(
            or_(
                and_(
                    models.Friend.requester_id == current_user.id,
                    models.Friend.addressee_id == goal.user_id,
                    models.Friend.status == models.FriendStatus.accepted
                ),
                and_(
                    models.Friend.requester_id == goal.user_id,
                    models.Friend.addressee_id == current_user.id,
                    models.Friend.status == models.FriendStatus.accepted
                )
            )
        )
        friend_result = await db.execute(friend_stmt)
        has_permission = friend_result.scalars().first() is not None
    
    if not has_permission:
        raise HTTPException(status_code=403, detail="You don't have permission to verify this request")
    
    # 3. Update the request status
    change_request.status = "approved" if verification.approved else "rejected"
    change_request.resolved_at = datetime.now(timezone.utc)
    change_request.resolved_by = current_user.id
    
    # 4. If approved, update the goal's milestone_interval_days
    if verification.approved:
        goal.milestone_interval_days = change_request.requested_interval
    
    # 5. Notify the requester
    status_text = "approved" if verification.approved else "rejected"
    await create_notification(
        db,
        recipient_id=change_request.requester_id,
        type=models.NotificationType.interval_change_request,
        message=f"{current_user.username} {status_text} your interval change request for '{goal.title}'",
        actor_id=current_user.id,
        goal_id=goal.id
    )
    
    await db.commit()
    
    return {
        "message": f"Interval change request {status_text}",
        "status": change_request.status,
        "new_interval": goal.milestone_interval_days if verification.approved else None
    }
```

---

#### [MODIFY] `/root/backend/app/api/router.py`

Add the new interval changes router:

```python
# Add this import
from app.api import interval_changes

# Add this line with other router includes (around line 15)
router.include_router(interval_changes.router, prefix="/interval-changes", tags=["interval-changes"])
```

---

### Component 5: Frontend - API Client

#### [MODIFY] `/root/frontend/src/lib/api.ts`

Add the interval change API functions. Insert after the `notificationsAPI` object (around line 199):

```typescript
// Interval Change API
export const intervalChangeAPI = {
  create: async (goalId: string, requestedInterval: number) =>
    (await api.post('/interval-changes', { goal_id: goalId, requested_interval: requestedInterval })).data,
  
  listPending: async () =>
    (await api.get('/interval-changes/pending')).data,
  
  verify: async (requestId: string, approved: boolean, comment?: string) =>
    (await api.post(`/interval-changes/${requestId}/verify`, { approved, comment })).data,
};
```

---

### Component 6: Frontend - GoalDetailView Update

#### [MODIFY] `/root/frontend/src/components/goals/GoalDetailView.tsx`

**Update 1**: Add the import for the new API (line 2):

Change:
```typescript
import { goalsAPI, proofsAPI, goalViewersAPI } from '../../lib/api';
```
To:
```typescript
import { goalsAPI, proofsAPI, goalViewersAPI, intervalChangeAPI } from '../../lib/api';
```

**Update 2**: Replace the `handleIntervalChangeRequest` function (lines 152-161):

Change:
```typescript
const handleIntervalChangeRequest = () => {
  if (!newInterval) {
    toast.error('Please select an interval first');
    return;
  }
  toast.success(`Interval change request sent to ${(goal.verifying_partners && goal.verifying_partners.length > 0 ? goal.verifying_partners[0].username : 'your goal buddies')} for approval!`, {
    description: 'They will need to approve before the change takes effect.',
  });
  setIntervalChangeOpen(false);
};
```

To:
```typescript
const handleIntervalChangeRequest = async () => {
  if (!newInterval) {
    toast.error('Please select an interval first');
    return;
  }
  
  setLoading(true);
  try {
    await intervalChangeAPI.create(goal.id, newInterval);
    toast.success(`Interval change request sent to ${(goal.verifying_partners && goal.verifying_partners.length > 0 ? goal.verifying_partners[0].username : 'your goal buddies')} for approval!`, {
      description: 'They will need to approve before the change takes effect.',
    });
    setIntervalChangeOpen(false);
  } catch (error: any) {
    console.error('Failed to send interval change request:', error);
    toast.error(error.response?.data?.detail || 'Failed to send interval change request');
  } finally {
    setLoading(false);
  }
};
```

---

### Component 7: Frontend - VerificationQueue Update

#### [MODIFY] `/root/frontend/src/components/proof/VerificationQueue.tsx`

**Update 1**: Add import for interval change API (line 2):

Change:
```typescript
import { proofsAPI, notificationsAPI } from '../../lib/api';
```
To:
```typescript
import { proofsAPI, notificationsAPI, intervalChangeAPI } from '../../lib/api';
```

**Update 2**: Add a new interface for interval change requests after the existing imports (around line 3):

```typescript
interface IntervalChangeRequest {
  id: string;
  goal_id: string;
  goal_title: string;
  requester_id: string;
  requester_name: string;
  current_interval: number;
  requested_interval: number;
  status: string;
  created_at: string;
}
```

**Update 3**: Add state for interval change requests (after line 32):

```typescript
const [intervalChangeRequests, setIntervalChangeRequests] = useState<IntervalChangeRequest[]>([]);
```

**Update 4**: Add function to load interval change requests (after the `loadProofs` function, around line 63):

```typescript
const loadIntervalChangeRequests = async () => {
  try {
    const data = await intervalChangeAPI.listPending();
    setIntervalChangeRequests(data || []);
  } catch (error) {
    console.error('Failed to load interval change requests:', error);
  }
};
```

**Update 5**: Add `loadIntervalChangeRequests()` call in the useEffect (line 77):

```typescript
useEffect(() => {
  if (typeof window !== 'undefined') {
    const user = localStorage.getItem('user');
    if (user) {
      try {
        setCurrentUserId(JSON.parse(user).id);
      } catch (error) {
        console.error('Failed to parse user from localStorage', error);
      }
    }
  }
  loadProofs();
  loadUnreadCount();
  loadIntervalChangeRequests();  // Add this line
}, []);
```

**Update 6**: Add handler for verifying interval change requests (after `handleVerifyGoalCompletion`, around line 146):

```typescript
const handleVerifyIntervalChange = async (requestId: string, approved: boolean) => {
  setLoading(true);
  try {
    await intervalChangeAPI.verify(requestId, approved);
    toast.success(approved ? 'Interval change approved!' : 'Interval change rejected');
    await loadIntervalChangeRequests();
  } catch (error: any) {
    console.error('Interval change verification failed:', error);
    toast.error(error.response?.data?.detail || 'Verification failed');
  } finally {
    setLoading(false);
  }
};
```

**Update 7**: Add interval change requests section in the "Friends' Pending" tab (after line 266, before the closing `</TabsContent>`):

```tsx
{/* Interval Change Requests Section */}
{intervalChangeRequests.length > 0 && (
  <div className="space-y-4 mt-6">
    <div>
      <h3>Interval Change Requests ({intervalChangeRequests.length})</h3>
      <p className="text-sm text-gray-600">Approve or reject check-in interval changes</p>
    </div>
    
    {intervalChangeRequests.map((request) => (
      <Card key={request.id} className="overflow-hidden border-orange-200">
        <CardHeader>
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <Avatar>
                <AvatarImage src={`https://api.dicebear.com/7.x/avataaars/svg?seed=${request.requester_name}`} />
                <AvatarFallback>{request.requester_name?.[0] || 'U'}</AvatarFallback>
              </Avatar>
              <div>
                <CardTitle className="text-lg">{request.requester_name}</CardTitle>
                <CardDescription>
                  {formatDistanceToNow(new Date(request.created_at), { addSuffix: true })}
                </CardDescription>
              </div>
            </div>
            <Badge variant="secondary" className="bg-orange-100 text-orange-800">
              <Clock className="h-3 w-3 mr-1" />
              Interval Change
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="text-sm font-medium text-gray-900">{request.goal_title}</p>
            <p className="text-sm text-gray-600 mt-1">
              Requesting to change check-in interval from{' '}
              <span className="font-medium">{request.current_interval} days</span> to{' '}
              <span className="font-medium text-orange-600">{request.requested_interval} days</span>
            </p>
          </div>
          
          <div className="flex gap-2">
            <Button
              onClick={() => handleVerifyIntervalChange(request.id, true)}
              className="flex-1 bg-green-600 hover:bg-green-700"
              disabled={loading}
            >
              <CheckCircle2 className="h-4 w-4 mr-2" />
              Approve
            </Button>
            <Button
              variant="outline"
              onClick={() => handleVerifyIntervalChange(request.id, false)}
              className="flex-1 border-red-300 text-red-700 hover:bg-red-50"
              disabled={loading}
            >
              <XCircle className="h-4 w-4 mr-2" />
              Reject
            </Button>
          </div>
        </CardContent>
      </Card>
    ))}
  </div>
)}
```

---

## Verification Plan

### Manual Verification Steps

Since there are no existing automated tests in this codebase, verification should be done manually:

1. **Database Migration Verification**:
   - After creating the migration, run `alembic upgrade head` in `/root/backend`
   - Verify the `interval_change_requests` table was created in the database

2. **Backend API Verification**:
   - Start the backend server: `cd /root/backend && uvicorn app.main:app --reload`
   - Use a tool like `curl` or Postman to test the endpoints:
     - `POST /api/v1/interval-changes` - Create a request
     - `GET /api/v1/interval-changes/pending` - List pending requests
     - `POST /api/v1/interval-changes/{id}/verify` - Approve/reject

3. **Frontend Integration Verification**:
   - Start the frontend: `cd /root/frontend && npm run dev`
   - Login as a user with a non-private goal that has accountability partners
   - Navigate to the goal detail view
   - Click "Change" next to the check-in interval
   - Select a new interval and click "Request Approval"
   - Verify the request was sent (check network tab for API call)

4. **Accountability Partner Verification**:
   - Login as the accountability partner
   - Navigate to the "Verify" tab
   - Under "I Need to Approve" (or "Friends' Pending"), look for the interval change request card
   - Click "Approve" or "Reject"
   - Verify the goal owner's interval is updated (if approved)

5. **Notification Verification**:
   - Check that notifications are created for both:
     - When the request is created (sent to accountability partner)
     - When the request is approved/rejected (sent to goal owner)

---

## Summary of Files to Change

| Action | File Path |
|--------|-----------|
| MODIFY | `/root/backend/app/db/models.py` |
| NEW | `/root/backend/app/alembic/versions/[timestamp]_add_interval_change_requests.py` |
| NEW | `/root/backend/app/schemas/interval_change.py` |
| NEW | `/root/backend/app/api/interval_changes.py` |
| MODIFY | `/root/backend/app/api/router.py` |
| MODIFY | `/root/frontend/src/lib/api.ts` |
| MODIFY | `/root/frontend/src/components/goals/GoalDetailView.tsx` |
| MODIFY | `/root/frontend/src/components/proof/VerificationQueue.tsx` |

> [!IMPORTANT]
> After making the backend changes, remember to run the Alembic migration:
> ```bash
> cd /root/backend
> alembic revision --autogenerate -m "add interval change requests table"
> alembic upgrade head
> ```
