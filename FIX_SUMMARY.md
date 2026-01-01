# Fix Summary: Response Validation Error on GET /api/v1/goals

## Problem
The backend was returning a 500 Internal Server Error when accessing `GET /api/v1/goals` with the following error:
```
fastapi.exceptions.ResponseValidationError: 1358 validation errors:
{'type': 'bool_type', 'loc': ('response', 0, 'milestones', 0, 'failed'), 'msg': 'Input should be a valid boolean', 'input': None}
```

## Root Cause
The `failed` column was added to the `milestones` table in migration `4c51bc27cf8e_add_failed_column_to_milestones.py` as **nullable=True**. This caused existing milestones to have NULL values for the `failed` field.

When the API tried to serialize these milestones using Pydantic's `MilestoneOut` schema (which expects `failed: bool`), it failed because Pydantic cannot convert NULL/None to a boolean.

**Database stats before fix:**
- Total milestones: 12,634
- Milestones with NULL failed: 12,577
- Milestones with failed value: 57

## Solution

### 1. Created New Migration
Created migration `2df9fcb63cd3_set_failed_default_and_make_non_nullable.py` that:
- Sets all NULL `failed` values to `FALSE` for existing milestones
- Alters the column to be `non-nullable` with a server default of `FALSE`

### 2. Fixed Schema Issues
- Removed incorrectly placed `recent_milestones` property from `MilestoneOut` class
- Added proper validator in `GoalListOut` to compute `recent_milestones` from milestones list

## Files Modified

1. **`app/alembic/versions/2df9fcb63cd3_set_failed_default_and_make_non_nullable.py`** (created)
   - Updates existing milestones with NULL failed values
   - Makes column non-nullable with server default

2. **`app/schemas/goal.py`**
   - Removed broken `recent_milestones` property from `MilestoneOut`
   - Added validator to compute `recent_milestones` in `GoalListOut`
   - Added import for `validator` from pydantic

## Verification

After running the migration:
```sql
SELECT 
    COUNT(*) as total,
    COUNT(CASE WHEN failed IS NULL THEN 1 END) as null_failed
FROM milestones;

-- Result: total: 12634, null_failed: 0
```

**All milestones now have valid boolean values for both `completed` and `failed` fields.**

## Testing
Restarted the backend server to pick up schema changes. The `/api/v1/goals` endpoint should now work correctly without validation errors.
