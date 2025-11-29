# Friend System Bug Fix Summary

## Issues Identified

There were **three bugs** preventing the friend system from working correctly:

### Bug 1: Wrong Status Filter in Line 132
**Location**: `/root/frontend/src/components/social/SocialPage.tsx:132`

**Problem**: 
```typescript
const incomingRequests = data.filter(f => f.status === 'pending'); // ❌ WRONG
```

The backend API returns `status = 'pending_received'` for incoming requests, but the frontend was checking for `'pending'` which doesn't exist.

### Bug 2: Wrong Status Filter in Line 148
**Location**: `/root/frontend/src/components/social/SocialPage.tsx:148`

**Problem**:
```typescript
const incomingRequests = friends.filter(f => f.status === 'pending' && ...); // ❌ WRONG
```

Same issue - filtering for non-existent `'pending'` status instead of `'pending_received'`.

### Bug 3: Duplicate Data Loading
**Location**: `/root/frontend/src/components/social/SocialPage.tsx:125-145`

**Problem**: The component was loading friend data **twice** on mount:
1. `loadFriends()` (line 121-123) - loads all relationships and separates them correctly
2. `loadIncomingRequests()` (line 125-145) - loads again and appends duplicates

This created race conditions and state inconsistencies where incoming requests might be added multiple times or overwritten.

## Backend API Behavior (Correct)

The backend `/friends` endpoint correctly returns different status values based on perspective:

**When User A sends request to User B:**
- For **User A** (sender): `{ status: "pending_sent", ... }`
- For **User B** (receiver): `{ status: "pending_received", ... }`

**When request is accepted:**
- For both users: `{ status: "accepted", ... }`

## The Fix

### Changes Made:

1. **Removed duplicate useEffect** (lines 125-145)
   - Deleted the `loadIncomingRequests` function
   - Rely on single `loadFriends()` call

2. **Fixed status filter** (line 128)
   ```typescript
   // Before:
   const incomingRequests = friends.filter(f => f.status === 'pending' && ...);
   
   // After:
   const incomingRequests = friends.filter(f => f.status === 'pending_received');
   ```

3. **Updated loadFriends to handle all statuses correctly**
   ```typescript
   const friends = data.filter(f => f.status === 'accepted');
   const outgoingData = data.filter(f => f.status === 'pending_sent');
   // incoming requests (pending_received) stay in the main friends array
   ```

## Expected Behavior After Fix

### User A (Sender) Perspective:
1. Search for User B by email
2. Click "Add Friend" → Shows "Friend request sent to User B"
3. Go to "Requests" tab → See User B in "Outgoing Requests" section with "Pending" status
4. When User B accepts → User B moves to "My Friends" tab

### User B (Receiver) Perspective:
1. Receives toast notification: "User A sent you a friend request"
2. Clicks "View Request" or goes to Social → "Requests" tab
3. See User A in "Incoming Requests" section with Accept/Reject buttons
4. Clicks Accept → Toast "Friend request accepted!" 
5. User A appears in "My Friends" tab

## Verification Steps

To verify the fix works:

1. **Login as test1@gmail.com** (sender)
2. **Search for phiol.he@duke.edu**
3. **Click "Add Friend"**
   - Should see success toast
   - Should see the request in "Requests" tab under "Outgoing Requests"

4. **Login as phiol.he@duke.edu** (receiver)
5. **Go to Social tab → "Requests"**
   - Should see test1@gmail.com in "Incoming Requests"
   - Should see Accept and Reject buttons
6. **Click Accept**
   - Should see success toast
   - test1@gmail.com should appear in "My Friends" tab

7. **Login back as test1@gmail.com**
8. **Check "My Friends" tab**
   - phiol.he@duke.edu should appear as a friend

## Impact

These bugs caused:
- ❌ Senders couldn't see their pending sent requests
- ❌ Receivers couldn't see incoming friend requests  
- ❌ Accept/Reject buttons never appeared for receivers
- ❌ The "Requests" tab would appear empty even when requests existed

**After fix:**
- ✅ Senders see pending requests in "Outgoing Requests"
- ✅ Receivers see incoming requests with Accept/Reject buttons
- ✅ Both parties see correct statuses based on perspective
- ✅ Single source of truth for friend data (no duplicates)
