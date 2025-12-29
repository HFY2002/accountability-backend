# Fix 422 Error When Adding Allowed Viewers

## Problem Summary

When a user clicks "Add Friend as Viewer" on the Goal Details page (for goals with `select_friends` privacy setting), a 422 Unprocessable Entity error occurs. The backend log shows:
```
POST /api/v1/goals/{goal_id}/allowed-viewers HTTP/1.1" 422 Unprocessable Entity
```

## Root Cause Analysis

The 422 error is caused by a **mismatch between how the frontend sends data and how the backend expects to receive it**.

### Frontend Behavior
The frontend (`/root/frontend/src/lib/api.ts` lines 172-173) sends `viewer_id` in the **request body** as JSON:
```typescript
addAllowedViewer: async (goalId: string, userId: string) => 
    (await api.post(`/goals/${goalId}/allowed-viewers`, { viewer_id: userId })).data,
```

### Backend Expectation
The backend (`/root/backend/app/api/goal_viewers.py` lines 68-73) expects `viewer_id` as a **query parameter**:
```python
@router.post("/goals/{goal_id}/allowed-viewers", response_model=social_schemas.FriendOut)
async def add_goal_allowed_viewer(
    goal_id: UUID,
    viewer_id: UUID,  # This is interpreted as a QUERY parameter, not body!
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
```

In FastAPI, a simple type-annotated parameter (without `Body()`, `Query()`, or a Pydantic model) is treated as a **query parameter** by default. Since the frontend sends JSON in the body but the backend expects a query parameter, FastAPI returns a 422 validation error.

## Proposed Changes

### Backend Fix

> **IMPORTANT:** The recommended solution is to fix the backend to accept the viewer_id from the request body using a Pydantic schema, which is more RESTful for POST requests.

#### [NEW] `/root/backend/app/schemas/goal_viewers.py`

Create a new schema file for goal viewer request/response models:

```python
from pydantic import BaseModel
from uuid import UUID

class AllowedViewerAddIn(BaseModel):
    viewer_id: UUID
```

---

#### [MODIFY] `/root/backend/app/api/goal_viewers.py`

Update the `add_goal_allowed_viewer` endpoint to use the Pydantic model for the request body:

**Change lines 1-9** - Add import for the new schema:
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from uuid import UUID

from app.api import deps
from app.db import models
from app.schemas import social as social_schemas
from app.schemas.goal_viewers import AllowedViewerAddIn  # ADD THIS LINE

router = APIRouter()
```

**Change lines 68-74** - Update function signature to accept body parameter:
```python
@router.post("/goals/{goal_id}/allowed-viewers", response_model=social_schemas.FriendOut)
async def add_goal_allowed_viewer(
    goal_id: UUID,
    viewer_data: AllowedViewerAddIn,  # CHANGE: Use Pydantic model instead of bare UUID
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
```

**Change lines 90-114** - Update references from `viewer_id` to `viewer_data.viewer_id`:
```python
    # Verify that viewer_id is a friend
    friendship_stmt = select(models.Friend).where(
        or_(
            and_(
                models.Friend.requester_id == current_user.id,
                models.Friend.addressee_id == viewer_data.viewer_id,  # CHANGE
                models.Friend.status == models.FriendStatus.accepted
            ),
            and_(
                models.Friend.requester_id == viewer_data.viewer_id,  # CHANGE
                models.Friend.addressee_id == current_user.id,
                models.Friend.status == models.FriendStatus.accepted
            )
        )
    )
    friendship_result = await db.execute(friendship_stmt)
    friendship = friendship_result.scalars().first()
    
    if not friendship:
        raise HTTPException(status_code=400, detail="You can only add friends as allowed viewers")
    
    # Check if already added
    existing_stmt = select(models.GoalAllowedViewer).where(
        models.GoalAllowedViewer.goal_id == goal_id,
        models.GoalAllowedViewer.user_id == viewer_data.viewer_id  # CHANGE
    )
```

**Change lines 120-132** - Update remaining references:
```python
    # Add the viewer
    allowed_viewer = models.GoalAllowedViewer(
        goal_id=goal_id,
        user_id=viewer_data.viewer_id,  # CHANGE
        can_verify=True
    )
    db.add(allowed_viewer)
    await db.commit()
    
    # Get user details for response
    user_stmt = select(models.User).where(models.User.id == viewer_data.viewer_id)  # CHANGE
    user_result = await db.execute(user_stmt)
    user = user_result.scalars().first()
    
    profile_stmt = select(models.UserProfile).where(
        models.UserProfile.user_id == viewer_data.viewer_id  # CHANGE
    )
```

## Verification Plan

### Manual Verification (Required)

Since this is a backend API fix that affects frontend integration, the user should manually test:

1. **Start the backend server** (if not already running):
   ```bash
   cd /root/backend
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Start the frontend** (if not already running):
   ```bash
   cd /root/frontend
   npm run dev
   ```

3. **Test the fix**:
   - Log in to the application
   - Navigate to a goal with `select_friends` privacy setting (or create one)
   - In the "Allowed Viewers" section, click "Add Friend as Viewer"
   - Select a friend from the dropdown
   - Click "Add Viewer"
   - **Expected**: The friend should be added successfully with a toast message "Friend added as viewer"
   - **Verify**: The friend should now appear in the allowed viewers list

4. **Verify backend logs**:
   - Check that the POST request now returns 200 OK instead of 422
   - The log should show: `POST /api/v1/goals/{goal_id}/allowed-viewers HTTP/1.1" 200 OK`

### API Test (Optional - via curl)

Test the endpoint directly:
```bash
# Replace with actual values
export TOKEN="your_jwt_token"
export GOAL_ID="93de8d1e-7207-46a0-9980-926a168edd71"
export VIEWER_ID="friend_user_id"

curl -X POST "http://localhost:8000/api/v1/goals/${GOAL_ID}/allowed-viewers" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"viewer_id": "'${VIEWER_ID}'"}'
```

**Expected**: Returns 200 with the added viewer's details in JSON format.
