# Implementation Plan - Unadd Friend Feature

This plan outlines the steps to implement the "Unadd Friend" functionality in the Accountability App. This involves adding a new backend endpoint to remove a friendship and updating the frontend to include a "Unadd Friend" button with a confirmation dialog.

## User Review Required

> [!IMPORTANT]
> **Data Deletion**: The proposed backend change performs a **hard delete** on the `Friend` record. This removes the connection permanently. Ensure this aligns with the data retention policy. If a "soft delete" (setting status to 'deleted' or similar) is preferred, specific requirements for that behavior are needed (e.g., handling re-adding friends later).

## Proposed Changes

### Backend

#### [Modify] [root/backend/app/api/social.py]

- Add a new `DELETE` endpoint to remove an existing friendship.
- **Endpoint**: `/requests/{friendship_id}` is for requests. We should add `/friends/{friendship_id}` to specifically handle established friendships, or use a generic delete if preferred. Given the current structure, adding it as a top-level resource under the router makes sense.
- **Logic**:
    - Validate `friendship_id`.
    - Verification that the requesting user is part of the friendship (either requester or addressee).
    - Hard delete the `Friend` record from the database.
    - Return a 204 No Content status on success.

```python
@router.delete("/friends/{friendship_id}", status_code=204)
async def remove_friend(
    friendship_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """Remove a friend (delete the friendship)."""
    # Logic to find and delete friendship
```

### Frontend

#### [Modify] [root/frontend/src/lib/api.ts]

- Update `socialAPI` object to include the `removeFriend` method.

```typescript
export const socialAPI = {
  // ... existing methods
  removeFriend: async (friendshipId: string) => (await api.delete(`/friends/friends/${friendshipId}`)).data, // Note: Router prefix might apply
};
```
*Note: The backend router is likely mounted with a prefix. If `social.py` is mounted at `/friends`, then `@router.delete("/{friendship_id}")` would effectively be `/friends/{friendship_id}`.*

#### [Modify] [root/frontend/src/components/social/SocialPage.tsx]

- **Imports**:
    - Import `AlertDialog` components from `../ui/alert-dialog`.
    - Import `UserMinus` or `Trash2` icon from `lucide-react`.
- **State**:
    - Add state to track the friend selected for deletion (e.g., `const [friendToDelete, setFriendToDelete] = useState<string | null>(null)`).
- **Handlers**:
    - Create `handleUnaddFriend` function:
        - Call `socialAPI.removeFriend(friendId)`.
        - On success, show toast and update local `friends` state to remove the item.
        - On error, show error toast.
        - Close the dialog.
- **UI**:
    - Update the "My Friends" list item to include a "Unadd Friend" button (variant `destructive` or `outline` with destructive text).
    - Add the `AlertDialog` component at the end of the return statement (or within the component tree), controlled by the `friendToDelete` state.

## Verification Plan

### Automated Tests
*None planned as per "No edits" instruction, but typically would involve:*
- **Backend**: API test ensuring `DELETE` removes the record and enforces permissions.
- **Frontend**: Component test clicking the button and verifying the API call.

### Manual Verification
1.  **Start Application**: Ensure backend and frontend are running.
2.  **Navigate to Social**: Go to the "Social" tab.
3.  **View Friends**: Ensure "My Friends" list is populated.
4.  **Click Unadd**: Click the "Unadd Friend" button for a specific user.
5.  **Verify Dialog**: Confirm that a popup asks "Are you sure you want to delete this friend?" with "Yes" and "No".
6.  **Cancel**: Click "No". Verify the dialog closes and friend remains.
7.  **Confirm**: Click "Unadd" again, then click "Yes".
8.  **Verify Removal**:
    - Verify the user is immediately removed from the list.
    - Refresh the page to ensure the change is persisted (backend verification).
    - Check the "Add Friend" search to see if you can send a request to them again (verifying relationship is gone).
