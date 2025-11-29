# Friend System Backend Implementation

## Overview

This implementation adds complete friend system functionality to the backend, enabling users to:
- Search for friends by email
- Send friend requests
- View friend list and pending requests
- Accept or decline friend requests
- See proper friendship statuses

## API Endpoints

### 1. Search Users by Email

```
GET /api/v1/users/search?email=<query>
```

**Description:** Search for users by email address to find potential friends.

**Query Parameters:**
- `email` (required): Email search query (partial match supported)

**Response:**
```json
[
  {
    "id": "uuid-string",
    "email": "user@example.com",
    "username": "john_doe",
    "avatar_url": "https://example.com/avatar.jpg",
    "is_friend": false,
    "has_pending_request": false
  }
]
```

**Status Codes:**
- 200: Success
- 400: Invalid query
- 401: Authentication required

### 2. Send Friend Request

```
POST /api/v1/friends/requests
```

**Description:** Send a friend request to a target user.

**Request Body:**
```json
{
  "target_user_id": "uuid-string"
}
```

**Response:**
```json
{
  "id": "friendship-uuid",
  "user_id": "target-user-uuid",
  "name": "target_username",
  "email": "target@example.com",
  "avatar": "https://example.com/avatar.jpg",
  "status": "pending_sent",
  "added_at": "2025-11-25T08:00:00Z"
}
```

**Features:**
- Automatically accepts if there's a pending request in reverse
- Sends notifications to the target user

**Status Codes:**
- 201: Success
- 400: Invalid request
- 401: Authentication required
- 409: Duplicate request

### 3. List Friends and Requests

```
GET /api/v1/friends
```

**Description:** Get all friends and friend requests for the current user.

**Response:**
```json
[
  {
    "id": "friendship-uuid",
    "user_id": "friend-uuid",
    "name": "friend_username",
    "email": "friend@example.com",
    "avatar": "https://example.com/avatar.jpg",
    "status": "accepted|pending_sent|pending_received",
    "added_at": "2025-11-25T08:00:00Z"
  }
]
```

**Status Values:**
- `accepted`: Mutual friendship
- `pending_sent`: User sent the request, waiting for response
- `pending_received`: User received the request, needs to accept/decline

**Status Codes:**
- 200: Success
- 401: Authentication required

### 4. Accept Friend Request

```
POST /api/v1/friends/requests/{friendship_id}/accept
```

**Description:** Accept a pending friend request.

**Path Parameters:**
- `friendship_id`: The UUID of the friend request to accept

**Response:**
```json
{
  "id": "friendship-uuid",
  "user_id": "requester-uuid",
  "name": "requester_username",
  "email": "requester@example.com",
  "avatar": "https://example.com/avatar.jpg",
  "status": "accepted",
  "added_at": "2025-11-25T08:00:00Z"
}
```

**Features:**
- Sends notification to the requester
- Updates friendship status to accepted

**Status Codes:**
- 200: Success
- 401: Authentication required
- 403: Permission denied
- 404: Request not found

### 5. Decline Friend Request

```
DELETE /api/v1/friends/requests/{friendship_id}/decline
```

**Description:** Decline a pending friend request.

**Path Parameters:**
- `friendship_id`: The UUID of the friend request to decline

**Response:**
- 204 No Content

**Status Codes:**
- 204: Success
- 401: Authentication required
- 403: Permission denied
- 404: Request not found

## Database Schema

### Friend Model

```python
class Friend(Base):
    __tablename__ = "friends"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requester_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    addressee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status = Column(Enum(FriendStatus), default=FriendStatus.pending)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

### FriendStatus Enum

```python
class FriendStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    blocked = "blocked"
```

## Frontend Integration Guide

### Step 1: Search for Users

```javascript
// Search for users by email
const searchUsers = async (emailQuery) => {
  const response = await fetch(`/api/v1/users/search?email=${encodeURIComponent(emailQuery)}`);
  const users = await response.json();
  return users;
};
```

### Step 2: Display Search Results

```javascript
// Show search results with friend status
users.forEach(user => {
  console.log(`User: ${user.username} (${user.email})`);
  console.log(`Is Friend: ${user.is_friend}`);
  console.log(`Has Pending Request: ${user.has_pending_request}`);
  
  if (!user.is_friend && !user.has_pending_request) {
    // Show "Add Friend" button
  }
});
```

### Step 3: Send Friend Request

```javascript
// Send friend request to a user
const sendFriendRequest = async (targetUserId) => {
  const response = await fetch('/api/v1/friends/requests', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target_user_id: targetUserId })
  });
  
  if (response.ok) {
    console.log('Friend request sent!');
  }
};
```

### Step 4: Display Friend List

```javascript
// Get friend list and pending requests
const getFriends = async () => {
  const response = await fetch('/api/v1/friends');
  const friends = await response.json();
  
  const acceptedFriends = friends.filter(f => f.status === 'accepted');
  const pendingSent = friends.filter(f => f.status === 'pending_sent');
  const pendingReceived = friends.filter(f => f.status === 'pending_received');
  
  return { acceptedFriends, pendingSent, pendingReceived };
};
```

### Step 5: Handle Friend Requests

```javascript
// Accept a friend request
const acceptFriendRequest = async (friendshipId) => {
  const response = await fetch(`/api/v1/friends/requests/${friendshipId}/accept`, {
    method: 'POST'
  });
  
  if (response.ok) {
    console.log('Friend request accepted!');
  }
};

// Decline a friend request
const declineFriendRequest = async (friendshipId) => {
  const response = await fetch(`/api/v1/friends/requests/${friendshipId}/decline`, {
    method: 'DELETE'
  });
  
  if (response.ok) {
    console.log('Friend request declined!');
  }
};
```

## Implementation Details

### Enhanced FriendOut Schema

The `FriendOut` schema now includes:
- `id`: Friendship relationship ID
- `user_id`: The other user's ID
- `name`: Other user's username
- `email`: Other user's email
- `avatar`: Other user's avatar URL (from profile)
- `status`: Friendship status (accepted/pending_sent/pending_received)
- `added_at`: When the friendship/requests was created

### New UserSearchResult Schema

The `UserSearchResult` schema provides:
- `id`: User ID
- `email`: User email
- `username`: User username
- `avatar_url`: User avatar URL
- `is_friend`: Whether already friends
- `has_pending_request`: Whether there's a pending request

### Auto-Accept Feature

When User A sends a request to User B:
1. If User B has a pending request to User A, it auto-accepts
2. Both users become friends immediately
3. Notifications are sent to both parties

### Notification Integration

The implementation integrates with the existing notification system:
- Friend request: Notifies target user when request is sent
- Friend request accepted: Notifies requester when request is accepted

## Testing

Run the test script to verify functionality:

```bash
# Create test users
python3 test_friend_system.py setup

# Test endpoints (requires running server)
python3 test_friend_system.py test

# Show implementation summary
python3 test_friend_system.py
```

## Security Considerations

- All endpoints require authentication
- Users can only manage their own friend requests
- Email search returns only basic public information
- Friend requests respect user privacy settings
- Proper error handling prevents unauthorized access

## Migration Notes

No database migration is required - the existing `Friend` model already supports all necessary functionality. The implementation enhances the existing schema with improved response formatting and additional endpoints.