# Backend Implementation Plan: Give Up Reason

## Objective
Add functionality to store a reason when a user gives up on a goal.

## 1. Database Schema
**File:** `/root/backend/app/db/models.py`

**Action:** Update the `Goal` class to include a `failure_reason` column.

**Code:**
```python
# In class Goal(Base):
# Add this line with other columns
failure_reason = Column(Text, nullable=True)
```

## 2. API Schemas
**File:** `/root/backend/app/schemas/goal.py`

**Action:**
1.  Define a new schema `GoalGiveUpIn` for the request body.
2.  Update `GoalListOut` and `GoalDetailOut` to include `failure_reason`.

**Code:**
```python
# Add this new class
class GoalGiveUpIn(BaseModel):
    failure_reason: str

# Update GoalListOut class
class GoalListOut(BaseModel):
    # ... existing fields ...
    # Add this field:
    failure_reason: Optional[str] = None

# Update GoalDetailOut class
class GoalDetailOut(BaseModel):
    # ... existing fields ...
    # Add this field:
    failure_reason: Optional[str] = None
```

## 3. Database Migration
**File:** `/root/backend/app/alembic/versions`

**Action:** Generate a new Alembic migration.

**Command:**
```bash
# Run this from /root/backend/app
alembic revision --autogenerate -m "add failure_reason to goals"
alembic upgrade head
```

## 4. API Endpoint
**File:** `/root/backend/app/api/goals.py`

**Action:** Update the `give_up_goal` function to accept the reason in the body and save it.

**Code:**
```python
@router.post("/{goal_id}/give-up")
async def give_up_goal(
    goal_id: str,
    # Add this parameter:
    body: schemas.GoalGiveUpIn,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """Mark a goal as failed/given up"""
    # ... existing query code ...
    stmt = select(models.Goal).where(
        models.Goal.id == goal_id,
        models.Goal.user_id == current_user.id
    )
    result = await db.execute(stmt)
    goal = result.scalars().first()

    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    goal.status = models.GoalStatus.failed
    goal.is_completed = True
    goal.completed_at = datetime.utcnow()
    # Add this line:
    goal.failure_reason = body.failure_reason

    await db.commit()
    return {"message": "Goal marked as failed", "status": goal.status}
```
