# Implementation Plan: Goal Features Enhancement

## Overview

This plan addresses three major feature enhancements for the accountability application:

1. **Backend - Recent Milestones Display**: Show the last 2 completed milestones and the most recent incomplete milestone on goal cards. Auto-fail milestones that have passed their due date.
2. **Frontend - Enhanced Date Picker**: Replace simple calendar popover with year/month input fields, followed by calendar selection, with a confirmation dialog before setting the deadline.
3. **Frontend - Time-Based Progress Bar**: Calculate goal progress based on days elapsed since start date rather than milestone completion percentage.

---

## Feature 1: Backend - Recent Milestones Display with Auto-Fail

### Problem Analysis

**Current State:**
- `GoalListOut` schema in `goal.py` (line 77-95) does NOT include milestones
- Frontend `GoalCard.tsx` (lines 191-205) displays "Recent Milestones:" but the backend `list_goals` endpoint doesn't load milestone data
- No mechanism exists to automatically fail milestones past their due date
- Milestones have a `due_date` field (nullable Date) but it's not being used for status tracking

**Requirements:**
- Display last 2 completed milestones + most recent incomplete milestone
- Auto-fail milestones past completion deadline
- Example: If milestones 1, 2, 3 are completed and milestone 4 is incomplete, show "Eat chocolate, Drink coffee, Proofread paper"

### Proposed Changes

#### Backend Component: Goals API

**File**: `/root/backend/app\api\goals.py`

##### Change 1.1: Add Auto-Fail Milestone Function

Add a new utility function before the `list_goals` endpoint (around line 169):

```python
async def auto_fail_overdue_milestones(db: AsyncSession, goal: models.Goal):
    """
    Auto-fail milestones that have passed their due_date.
    Returns the updated milestones list.
    """
    from datetime import date
    
    # Query milestones for this goal
    milestones_stmt = select(models.Milestone).where(
        models.Milestone.goal_id == goal.id,
        models.Milestone.completed == False,
        models.Milestone.due_date.isnot(None),
        models.Milestone.due_date < date.today()
    )
    
    result = await db.execute(milestones_stmt)
    overdue_milestones = result.scalars().all()
    
    for milestone in overdue_milestones:
        milestone.completed = True
        milestone.failed = True  # NEW FIELD - see schema changes below
        milestone.completed_at = datetime.utcnow()
    
    if overdue_milestones:
        await db.commit()
```

##### Change 1.2: Modify `list_goals` Endpoint

Modify the `list_goals` endpoint (lines 169-182) to:
1. Load milestones with `selectinload`
2. Call auto-fail function
3. Compute recent milestones string

```python
@router.get("", response_model=List[schemas.GoalListOut])
async def list_goals(
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """List all goals for the current user"""
    stmt = select(models.Goal).where(
        models.Goal.user_id == current_user.id,
        models.Goal.status != models.GoalStatus.archived
    ).options(
        selectinload(models.Goal.milestones)  # EAGER LOAD MILESTONES
    ).order_by(models.Goal.created_at.desc())
    
    result = await db.execute(stmt)
    goals = result.scalars().all()
    
    # Auto-fail overdue milestones and compute recent milestones for each goal
    for goal in goals:
        await auto_fail_overdue_milestones(db, goal)
    
    return goals
```

**IMPORTANT**: The auto-fail function must run BEFORE serializing goals to ensure the frontend receives updated milestone statuses.

#### Backend Component: Schemas

**File**: `/root/backend/app\schemas\goal.py`

##### Change 1.3: Add `failed` Field to MilestoneOut

Modify `MilestoneOut` class (lines 23-37):

```python
class MilestoneOut(BaseModel):
    id: UUID
    goal_id: UUID
    title: str
    description: Optional[str] = None
    batch_number: int
    is_flexible: bool
    order_index: int
    due_date: Optional[date] = None
    completed: bool
    failed: bool = False  # NEW FIELD
    progress: int
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
```

##### Change 1.4: Add `recent_milestones` Field to GoalListOut

Modify `GoalListOut` class (lines 77-95) to include milestones and computed recent_milestones:

```python
class GoalListOut(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    description: Optional[str]
    milestone_type: MilestoneType
    milestone_interval_days: Optional[int]
    start_date: date
    deadline: date
    privacy_setting: GoalPrivacy
    image_url: Optional[str]
    status: GoalStatus
    is_completed: bool
    milestone_quantity: Optional[int]
    milestone_unit: Optional[str]
    failure_reason: Optional[str] = None
    milestones: List[MilestoneOut] = []  # NEW: Include milestones
    recent_milestones: Optional[str] = None  # NEW: Computed field for display

    class Config:
        from_attributes = True
        
    @property
    def recent_milestones(self) -> str:
        """
        Returns a string with the last 2 completed milestones and the most recent incomplete milestone.
        Format: "Milestone2, Milestone3, Milestone4"
        """
        if not self.milestones:
            return ""
        
        # Sort milestones by order_index
        sorted_milestones = sorted(self.milestones, key=lambda m: m.order_index)
        
        # Get completed milestones (excluding failed ones)
        completed = [m for m in sorted_milestones if m.completed and not m.failed]
        
        # Get incomplete milestones (not completed and not failed)
        incomplete = [m for m in sorted_milestones if not m.completed and not m.failed]
        
        # Select last 2 completed
        last_two_completed = completed[-2:] if len(completed) >= 2 else completed
        
        # Select first incomplete (most recent one to work on)
        first_incomplete = incomplete[0:1] if incomplete else []
        
        # Combine them
        display_milestones = last_two_completed + first_incomplete
        
        # Return comma-separated titles
        return ", ".join([m.title for m in display_milestones])
```

**Note**: Pydantic's `@property` decorator creates a computed field that's automatically serialized in API responses.

#### Backend Component: Database Models

**File**: `/root/backend/app\db\models.py`

##### Change 1.5: Add `failed` Column to Milestone Model

Modify the `Milestone` class (lines 124-141):

```python
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
    failed = Column(Boolean, default=False)  # NEW FIELD
    progress = Column(Integer, default=0)
    completed_at = Column(DateTime(timezone=True))
    
    goal = relationship("Goal", back_populates="milestones")
    proofs = relationship("Proof", back_populates="milestone")
```

#### Backend Component: Database Migration

**File**: `/root/backend/app\alembic\versions\`

##### Change 1.6: Create Alembic Migration for `failed` Column

**CRITICAL**: After modifying the model, you MUST create a new Alembic migration and upgrade to head:

```bash
cd c:\Users\User\Desktop\frontend\accountability-backend
alembic revision --autogenerate -m "add_failed_column_to_milestones"
alembic upgrade head
```

The migration file should add:
```python
def upgrade():
    op.add_column('milestones', sa.Column('failed', sa.Boolean(), nullable=True))
    # Set default value for existing rows
    op.execute("UPDATE milestones SET failed = FALSE WHERE failed IS NULL")
    op.alter_column('milestones', 'failed', nullable=False, server_default='FALSE')

def downgrade():
    op.drop_column('milestones', 'failed')
```

---

### Frontend Component: GoalCard Display

**File**: `/root/frontend/src\components\goals\GoalCard.tsx`

##### Change 1.7: Update Milestone Display Section

Modify lines 189-206 to display the `recent_milestones` string from the backend:

**BEFORE:**
```typescript
{/* Milestone Progress */}
<div className="space-y-2">
  <p className="text-sm text-gray-600">Recent Milestones:</p>
  <div className="space-y-2">
    {goal.milestones && goal.milestones.slice(-3).reverse().map((milestone) => (
      <div key={milestone.id} className="flex items-center gap-2 text-sm">
        {milestone.completed ? (
          <CheckCircle2 className="h-4 w-4 text-green-600 flex-shrink-0" />
        ) : (
          <Circle className="h-4 w-4 text-gray-400 flex-shrink-0" />
        )}
        <span className={`line-clamp-1 ${milestone.completed ? 'text-green-600' : 'text-gray-600'}`}>
          {milestone.title}
        </span>
      </div>
    ))}
  </div>
</div>
```

**AFTER:**
```typescript
{/* Milestone Progress */}
<div className="space-y-2">
  <p className="text-sm text-gray-600">
    Recent Milestones: 
    <span className="ml-2 font-medium text-gray-800">
      {goal.recent_milestones || 'No milestones yet'}
    </span>
  </p>
</div>
```

---

## Feature 2: Frontend - Enhanced Date Picker with Confirmation

### Problem Analysis

**Current State:**
- `CreateGoalModal.tsx` uses basic `Popover` + `Calendar` components (lines 306-347)
- Users must click through months manually to reach distant dates
- No year/month input for faster navigation
- No confirmation dialog before setting deadline
- Deadline can be changed without warning

**Requirements:**
- Allow manual input of last 2 digits of year (e.g., "25" for 2025)
- Allow selection of month from dropdown
- Show calendar for selected year/month to pick exact date
- Start date must be before deadline chronologically
- Confirmation dialog with green "✅Confirm" and red "❌Cancel" buttons
- Warning: "The deadline of this project CANNOT be changed after you set it. You set the deadline yourself, you get the job done before it. Confirm when you are ready."
- If user clicks Cancel, return to date selection

### Proposed Changes

#### Frontend Component: Enhanced Date Picker

**File**: `/root/frontend/src\components\goals\CreateGoalModal.tsx`

##### Change 2.1: Add State for Enhanced Date Picker

Add new state variables after line 55:

```typescript
const [showYearMonthSelector, setShowYearMonthSelector] = useState(false);
const [yearInput, setYearInput] = useState('');
const [selectedMonth, setSelectedMonth] = useState<number | null>(null);
const [tempDeadline, setTempDeadline] = useState<Date | undefined>(undefined);
const [showDeadlineConfirmation, setShowDeadlineConfirmation] = useState(false);
const [datePickerMode, setDatePickerMode] = useState<'start' | 'deadline' | null>(null);
```

##### Change 2.2: Create Year-Month Selector Component

Add a new inline component before the return statement (around line 197):

```typescript
const YearMonthDatePicker = ({ 
  selectedDate, 
  onDateSelect, 
  minDate 
}: { 
  selectedDate: Date | undefined; 
  onDateSelect: (date: Date) => void;
  minDate?: Date;
}) => {
  const [year, setYear] = useState('');
  const [month, setMonth] = useState<number | null>(null);
  const [showCalendar, setShowCalendar] = useState(false);
  
  // Get current year last 2 digits as default
  const currentYear = new Date().getFullYear();
  const currentYearLast2 = currentYear.toString().slice(-2);
  
  const handleYearChange = (value: string) => {
    // Only allow 2 digits
    if (value.length <= 2 && /^\d*$/.test(value)) {
      setYear(value);
    }
  };
  
  const handleMonthSelect = (monthIndex: number) => {
    setMonth(monthIndex);
    // If year is set, show calendar
    if (year.length === 2) {
      setShowCalendar(true);
    }
  };
  
  const handleCalendarDateSelect = (date: Date | undefined) => {
    if (date) {
      onDateSelect(date);
      setShowCalendar(false);
    }
  };
  
  const fullYear = year.length === 2 ? parseInt('20' + year) : currentYear;
  const calendarMonth = month !== null ? new Date(fullYear, month, 1) : new Date();
  
  const months = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];
  
  if (showCalendar && year.length === 2 && month !== null) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">
            {months[month]} {fullYear}
          </span>
          <Button 
            variant="ghost" 
            size="sm"
            onClick={() => setShowCalendar(false)}
          >
            Change Month
          </Button>
        </div>
        <Calendar
          mode="single"
          selected={selectedDate}
          onSelect={handleCalendarDateSelect}
          month={calendarMonth}
          onMonthChange={() => {}} // Disable month navigation
          disabled={(date: Date) => {
            // Disable dates not in selected month
            if (date.getMonth() !== month || date.getFullYear() !== fullYear) {
              return true;
            }
            // Disable dates before minDate if provided
            if (minDate && date < minDate) {
              return true;
            }
            return false;
          }}
        />
      </div>
    );
  }
  
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Year (Last 2 Digits)</Label>
        <div className="flex items-center gap-2">
          <span className="text-2xl font-bold">20</span>
          <Input
            placeholder="__"
            value={year}
            onChange={(e) => handleYearChange(e.target.value)}
            maxLength={2}
            className="w-16 text-center text-lg font-mono"
          />
        </div>
        <p className="text-xs text-gray-500">
          Enter the last 2 digits (e.g., 25 for 2025)
        </p>
      </div>
      
      {year.length === 2 && (
        <div className="space-y-2">
          <Label>Select Month</Label>
          <div className="grid grid-cols-3 gap-2">
            {months.map((monthName, idx) => (
              <Button
                key={idx}
                variant={month === idx ? "default" : "outline"}
                size="sm"
                onClick={() => handleMonthSelect(idx)}
                className="text-xs"
              >
                {monthName}
              </Button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
```

##### Change 2.3: Replace Deadline Date Picker

Replace the deadline date picker section (lines 327-346) with the enhanced version:

```typescript
<div className="space-y-2">
  <Label>Deadline *</Label>
  <Popover>
    <PopoverTrigger asChild>
      <Button variant="outline" className="w-full justify-start">
        <CalendarIcon className="mr-2 h-4 w-4" />
        {tempDeadline || deadline ? format(tempDeadline || deadline, 'PPP') : 'Pick a date'}
      </Button>
    </PopoverTrigger>
    <PopoverContent className="w-auto p-4" align="start">
      <YearMonthDatePicker
        selectedDate={tempDeadline || deadline}
        onDateSelect={(date) => {
          setTempDeadline(date);
          setShowDeadlineConfirmation(true);
        }}
        minDate={startDate}
      />
    </PopoverContent>
  </Popover>
</div>
```

##### Change 2.4: Add Deadline Confirmation Dialog

Add the confirmation dialog component before the closing `</Dialog>` tag (around line 414):

```typescript
{/* Deadline Confirmation Dialog */}
<Dialog open={showDeadlineConfirmation} onOpenChange={setShowDeadlineConfirmation}>
  <DialogContent className="max-w-md">
    <DialogHeader>
      <DialogTitle className="text-red-600">⚠️ Deadline Confirmation</DialogTitle>
    </DialogHeader>
    
    <div className="space-y-4 py-4">
      <div className="bg-red-50 border-2 border-red-200 rounded-lg p-4">
        <p className="text-sm text-red-900 font-medium">
          The deadline of this project <strong>CANNOT be changed</strong> after you set it. 
          You set the deadline yourself, you get the job done before it.
        </p>
        <p className="text-sm text-red-800 mt-2">
          Confirm when you are ready.
        </p>
      </div>
      
      {tempDeadline && (
        <div className="bg-gray-50 p-3 rounded-lg">
          <p className="text-sm text-gray-600">Selected deadline:</p>
          <p className="text-lg font-bold">{format(tempDeadline, 'PPPP')}</p>
        </div>
      )}
    </div>
    
    <div className="flex gap-3 justify-end">
      <Button
        variant="destructive"
        onClick={() => {
          setShowDeadlineConfirmation(false);
          setTempDeadline(undefined);
        }}
        className="gap-2"
      >
        ❌ Cancel
      </Button>
      <Button
        variant="default"
        onClick={() => {
          if (tempDeadline) {
            setDeadline(tempDeadline);
            setShowDeadlineConfirmation(false);
          }
        }}
        className="gap-2 bg-green-600 hover:bg-green-700"
      >
        ✅ Confirm
      </Button>
    </div>
  </DialogContent>
</Dialog>
```

##### Change 2.5: Add the Same Enhanced Date Picker to Start Date (Optional Enhancement)

For consistency, the start date picker (lines 306-325) can OPTIONALLY use the same `YearMonthDatePicker` component. This is not required by the user but would improve UX:

```typescript
<div className="space-y-2">
  <Label>Start Date *</Label>
  <Popover>
    <PopoverTrigger asChild>
      <Button variant="outline" className="w-full justify-start">
        <CalendarIcon className="mr-2 h-4 w-4" />
        {startDate ? format(startDate, 'PPP') : 'Pick a date'}
      </Button>
    </PopoverTrigger>
    <PopoverContent className="w-auto p-4" align="start">
      <YearMonthDatePicker
        selectedDate={startDate}
        onDateSelect={setStartDate}
      />
    </PopoverContent>
  </Popover>
</div>
```

---

## Feature 3: Frontend - Time-Based Progress Calculation

### Problem Analysis

**Current State:**
- `GoalCard.tsx` (lines 39-41) calculates progress as average of `milestone.progress` values
- `milestone.progress` field defaults to 0 and is never updated, so progress always shows 0%
- The circular progress bar (lines 108-153) displays this incorrect value

**Requirements:**
- Calculate progress as: `(days elapsed since start date) / (total days from start to deadline) * 100`
- Update circular progress bar to fill clockwise according to this percentage
- Display numerical percentage inside the circle

**Formula**:
```
days_elapsed = today - start_date
total_days = deadline - start_date
progress_percentage = (days_elapsed / total_days) * 100

Clamp to 0-100 range:
- If today < start_date: progress = 0%
- If today > deadline: progress = 100%
- Otherwise: use calculated value
```

### Proposed Changes

#### Frontend Component: GoalCard

**File**: `/root/frontend/src\components\goals\GoalCard.tsx`

##### Change 3.1: Replace Progress Calculation

Replace lines 39-41 with the new time-based calculation:

**BEFORE:**
```typescript
const totalProgress = goal.milestones && goal.milestones.length > 0 
  ? goal.milestones.reduce((sum, m) => sum + (m.progress || 0), 0) / goal.milestones.length 
  : 0;
```

**AFTER:**
```typescript
// Calculate time-based progress
const calculateTimeBasedProgress = (): number => {
  const today = new Date();
  const startDate = new Date(goal.start_date);
  const deadlineDate = new Date(goal.deadline);
  
  // Reset time to midnight for accurate day counting
  today.setHours(0, 0, 0, 0);
  startDate.setHours(0, 0, 0, 0);
  deadlineDate.setHours(0, 0, 0, 0);
  
  // Calculate days
  const totalDays = Math.ceil((deadlineDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24));
  const daysElapsed = Math.ceil((today.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24));
  
  // Handle edge cases
  if (totalDays <= 0) return 0; // Invalid goal
  if (daysElapsed < 0) return 0; // Goal hasn't started yet
  if (daysElapsed > totalDays) return 100; // Past deadline
  
  // Calculate percentage
  const percentage = (daysElapsed / totalDays) * 100;
  return Math.max(0, Math.min(100, percentage)); // Clamp to 0-100
};

const totalProgress = calculateTimeBasedProgress();
```

##### Change 3.2: Update Tooltip Content (Optional Enhancement)

Optionally, update the tooltip (lines 142-150) to show time-based information instead of milestone progress:

**BEFORE:**
```typescript
<TooltipContent>
  <div className="text-sm space-y-1">
    {goal.milestones && goal.milestones.map((m) => (
      <div key={m.id}>
        {m.title}: {m.progress}%
      </div>
    ))}
  </div>
</TooltipContent>
```

**AFTER:**
```typescript
<TooltipContent>
  <div className="text-sm space-y-1">
    <div>
      <strong>Time Progress:</strong> {Math.round(totalProgress)}%
    </div>
    <div className="text-xs text-gray-400">
      {completedMilestones} of {goal.milestones?.length || 0} milestones completed
    </div>
  </div>
</TooltipContent>
```

---

## Verification Plan

### Automated Tests

**No existing test infrastructure was found in the codebase.** The following verification will require manual testing by the user or creation of new test files.

If you want automated tests, you would need to:
1. Set up pytest for backend (create `tests/` directory)
2. Set up Jest/React Testing Library for frontend
3. Write unit tests for the new functions

**Recommendation**: Skip automated tests for now and rely on manual verification.

### Manual Verification

#### Test 1: Backend - Recent Milestones Display

**Prerequisites:**
- Backend server running: `cd c:\Users\User\Desktop\frontend\accountability-backend && uvicorn app.main:app --reload`
- Database migration completed: `alembic upgrade head`

**Steps:**
1. Create a test goal with at least 4 milestones using the API or frontend
2. Mark milestones 1, 2, 3 as completed (set `completed=True` via database or API)
3. Call `GET /goals/` API endpoint
4. **Expected Result**: 
   - Each goal object should have `recent_milestones` field
   - Value should be "Milestone2, Milestone3, Milestone4" (last 2 completed + first incomplete)

**Test with curl:**
```bash
curl -X GET "http://localhost:8000/goals/" \
  -H "Authorization: Bearer YOUR_TOKEN" | jq '.[] | .recent_milestones'
```

#### Test 2: Backend - Auto-Fail Overdue Milestones

**Prerequisites:**
- Backend server running
- Database with test data

**Steps:**
1. Create a goal with a milestone that has `due_date` set to yesterday
2. Ensure the milestone is NOT marked as completed
3. Call `GET /goals/` API endpoint
4. **Expected Result**:
   - The overdue milestone should have `completed=True` and `failed=True`
   - The milestone should NOT appear in `recent_milestones` (since failed milestones are excluded)

**Test with SQL:**
```sql
-- Before calling API
SELECT title, due_date, completed, failed FROM milestones WHERE due_date < CURRENT_DATE AND completed = FALSE;

-- After calling GET /goals/
SELECT title, due_date, completed, failed FROM milestones WHERE due_date < CURRENT_DATE;
-- All should have failed=TRUE
```

#### Test 3: Frontend - Enhanced Date Picker for Deadline

**Prerequisites:**
- Frontend running: `cd c:\Users\User\Desktop\frontend\accountability-frontend && npm run dev`
- User logged in

**Steps:**
1. Navigate to Goals page
2. Click "+ New Goal" button
3. Fill in goal title
4. Click on "Deadline *" field
5. **Expected**: Year-month selector appears with "20__" year input
6. Enter "25" in the year blanks
7. **Expected**: Month selection grid appears with 12 month buttons
8. Click on "December"
9. **Expected**: Calendar appears showing December 2025 only
10. Click on a date (e.g., December 15, 2025)
11. **Expected**: Red confirmation dialog appears with:
    - Warning message about deadline cannot be changed
    - Selected date displayed
    - "❌Cancel" button (red)
    - "✅Confirm" button (green)
12. Click "❌Cancel"
13. **Expected**: Returns to date picker, deadline not set
14. Repeat steps 5-10
15. Click "✅Confirm"
16. **Expected**: Deadline is set, dialog closes, button shows "December 15, 2025"

#### Test 4: Frontend - Start Date Must Be Before Deadline

**Prerequisites:**
- Frontend running
- User logged in

**Steps:**
1. Navigate to create goal modal
2. Set start date to "December 20, 2025"
3. Try to set deadline to "December 10, 2025"
4. **Expected**: Calendar should disable all dates before December 20, 2025

#### Test 5: Frontend - Time-Based Progress Calculation

**Prerequisites:**
- Frontend running
- Test goals with various start dates and deadlines

**Test Case 1: Goal started today, deadline in 10 days
**Steps:**
1. Create goal with start_date = today, deadline = today + 10 days
2. View goal card
3. **Expected**: Progress bar shows ~0-10% (depending on exact time of day)

**Test Case 2: Goal started 5 days ago, deadline in 5 days
**Steps:**
1. Create goal with start_date = today - 5 days, deadline = today + 5 days
2. View goal card
3. **Expected**: Progress bar shows ~50%

**Test Case 3: Goal started 10 days ago, deadline was yesterday
**Steps:**
1. Create goal with start_date = today - 10 days, deadline = yesterday
2. View goal card
3. **Expected**: Progress bar shows 100% (past deadline)

**Test Case 4: Goal hasn't started yet
**Steps:**
1. Create goal with start_date = tomorrow, deadline = next week
2. View goal card
3. **Expected**: Progress bar shows 0%

**Formula to verify manually:**
```
Days elapsed = Today - Start Date
Total days = Deadline - Start Date
Progress = (Days elapsed / Total days) * 100
```

**Visual Check:**
- Circular progress bar should fill clockwise
- Numerical value inside circle should match calculation
- Color should be blue (#2563eb)

---

## Critical Implementation Notes

### Execution Order

**MUST follow this exact order to avoid errors:**

1. **Database Changes First**:
   - Modify `models.py` to add `failed` column
   - Run `alembic revision --autogenerate -m "add_failed_to_milestones"`
   - Run `alembic upgrade head`

2. **Backend Schema Updates**:
   - Update `schemas/goal.py` to add `failed`, `recent_milestones`, and milestones list

3. **Backend API Logic**:
   - Add `auto_fail_overdue_milestones()` function
   - Modify `list_goals()` endpoint

4. **Frontend Changes**:
   - Update `GoalCard.tsx` for milestone display and progress calculation
   - Update `CreateGoalModal.tsx` for enhanced date picker

### Breaking Changes

> [!WARNING]
> **Frontend Breaking Change**: The `GoalListOut` schema will now include a `milestones` array. Ensure frontend code can handle this additional data.

> [!IMPORTANT]
> **Database Migration Required**: The `failed` column must be added to the `milestones` table before deploying backend changes. Failure to run the migration will cause 500 errors.

### Deadline Immutability

> [!CAUTION]
> **User Expectation**: The confirmation dialog warns users that deadlines cannot be changed. However, this plan does NOT implement backend enforcement of deadline immutability. If you want to enforce this:
> 
> 1. Modify `GoalUpdate` schema to exclude `deadline` field
> 2. Or add validation in `update_goal()` endpoint to reject deadline changes
> 
> **Recommendation**: Implement this backend validation in a follow-up task.

### Performance Considerations

> [!NOTE]
> **N+1 Query Prevention**: The `list_goals()` endpoint now uses `selectinload(models.Goal.milestones)` to eager-load milestones. This prevents N+1 query problems when calling `auto_fail_overdue_milestones()` for each goal.

### Edge Cases to Handle

1. **Goals with no milestones**: `recent_milestones` should return empty string
2. **All milestones completed**: Show last 3 completed milestones
3. **All milestones failed**: Show empty string (failed milestones excluded)
4. **Mixed completed/failed**: Only show non-failed milestones
5. **Exactly 1-2 completed milestones**: Show what's available + incomplete
6. **Progress calculation with same start and deadline**: Return 0% (invalid goal)

---

## Summary of Files to Modify

### Backend (6 changes + 1 migration)
1. `app/db/models.py` - Add `failed` column to `Milestone` model
2. `app/schemas/goal.py` - Add `failed` to `MilestoneOut`, add `milestones` and `recent_milestones` to `GoalListOut`
3. `app/api/goals.py` - Add `auto_fail_overdue_milestones()` function and modify `list_goals()` endpoint
4. `app/alembic/versions/XXXXX_add_failed_to_milestones.py` - NEW migration file

### Frontend (2 changes)
1. `src/components/goals/GoalCard.tsx` - Update milestone display and progress calculation
2. `src/components/goals/CreateGoalModal.tsx` - Add enhanced year-month date picker and confirmation dialog

### Total Changes
- **Backend**: 3 files modified + 1 new migration
- **Frontend**: 2 files modified
- **Database**: 1 column added

---

## Post-Implementation Validation

After implementing all changes, verify:

✅ All milestones past their `due_date` are automatically marked as `failed=True`  
✅ Failed milestones do not appear in `recent_milestones` display  
✅ Goal cards show format: "Milestone1, Milestone2, Milestone3"  
✅ Progress bars show time-based percentage (0-100%)  
✅ Progress calculation handles all edge cases (not started, past deadline, etc.)  
✅ Date picker allows year/month input before calendar  
✅ Deadline confirmation dialog appears with correct styling and buttons  
✅ Clicking Cancel returns to date picker without setting deadline  
✅ Clicking Confirm sets deadline and closes dialog  
✅ Start date validation prevents deadline from being before start date  

If any validation fails, review the corresponding section of this implementation plan.
