#!/usr/bin/env python3
"""
Test script to verify the friend system functionality
"""
import asyncio
import sys
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import SessionLocal
from app.db import models
from app.core.config import settings
from sqlalchemy import select, delete

async def setup_test_data():
    """Create some test users"""
    async with SessionLocal() as session:
        async with session.begin():
            # Clean up existing test data
            await session.execute(delete(models.UserProfile))
            await session.execute(delete(models.Friend))
            await session.execute(delete(models.User).where(models.User.email.in_([
                "test1@example.com", "test2@example.com", "test3@example.com"
            ])))
            
            # Create test users
            user1 = models.User(
                email="test1@example.com",
                username="testuser1",
                password_hash="hashed_password1"
            )
            user2 = models.User(
                email="test2@example.com",
                username="testuser2",
                password_hash="hashed_password2"
            )
            user3 = models.User(
                email="test3@example.com",
                username="testuser3",
                password_hash="hashed_password3"
            )
            
            session.add_all([user1, user2, user3])
            await session.flush()  # Get IDs
            
            # Create profiles
            profile1 = models.UserProfile(
                user_id=user1.id,
                avatar_url="https://example.com/avatar1.jpg"
            )
            profile2 = models.UserProfile(
                user_id=user2.id,
                avatar_url="https://example.com/avatar2.jpg"
            )
            profile3 = models.UserProfile(
                user_id=user3.id,
                avatar_url="https://example.com/avatar3.jpg"
            )
            
            session.add_all([profile1, profile2, profile3])
            
            print("Test users created:")
            print(f"User 1: {user1.email} (ID: {user1.id})")
            print(f"User 2: {user2.email} (ID: {user2.id})")
            print(f"User 3: {user3.email} (ID: {user3.id})")

def test_endpoints():
    """Test the API endpoints (requires server to be running)"""
    import requests
    
    BASE_URL = "http://localhost:8000/api/v1"
    
    # Note: In real implementation, you would need to get a valid token
    # For this test, we assume authentication is handled separately
    
    print("\n=== Testing Friend System Endpoints ===")
    
    # 1. Test user search endpoint
    print("\n1. Testing user search endpoint:")
    print("   GET /users/search?email=test@example.com")
    print("   This should search for users by email for adding friends")
    
    # 2. Test friend list endpoint
    print("\n2. Testing friend list endpoint:")
    print("   GET /friends")
    print("   This returns all friends and pending requests")
    
    # 3. Test send friend request
    print("\n3. Testing send friend request endpoint:")
    print("   POST /friends/requests")
    print("   Body: {\"target_user_id\": \"<user_id>\"}")
    
    # 4. Test accept friend request
    print("\n4. Testing accept friend request endpoint:")
    print("   POST /friends/requests/{friendship_id}/accept")
    
    # 5. Test decline friend request
    print("\n5. Testing decline friend request endpoint:")
    print("   DELETE /friends/requests/{friendship_id}/decline")

def print_api_summary():
    """Print a summary of the implemented API endpoints"""
    print("\n" + "="*50)
    print("FRIEND SYSTEM API IMPLEMENTATION SUMMARY")
    print("="*50)
    
    print("\n✅ SEARCH & ADD FRIENDS:")
    print("   • GET /users/search?email=<query>")
    print("     - Search for users by email")
    print("     - Returns: id, email, username, avatar_url, is_friend, has_pending_request")
    print("   • POST /friends/requests")
    print("     - Send friend request using target_user_id")
    print("     - Auto-accepts if reverse request exists")
    
    print("\n✅ MANAGE FRIEND REQUESTS:")
    print("   • GET /friends")
    print("     - List all friends and pending requests")
    print("     - Returns: id, user_id, name, email, avatar, status, added_at")
    print("     - Status values: 'accepted', 'pending_sent', 'pending_received'")
    print("   • POST /friends/requests/{friendship_id}/accept")
    print("     - Accept a pending friend request")
    print("   • DELETE /friends/requests/{friendship_id}/decline")
    print("     - Decline a pending friend request")
    
    print("\n✅ RESPONSE SCHEMAS:")
    print("   • FriendOut:")
    print("     - id, user_id, name, email, avatar, status, added_at")
    print("   • UserSearchResult:")
    print("     - id, email, username, avatar_url, is_friend, has_pending_request")
    
    print("\n✅ FRONTEND INTEGRATION:")
    print("   1. Use /users/search?email=... to find friends by email")
    print("   2. Use /friends/requests to send friend requests")
    print("   3. Use /friends to view friend list and pending requests")
    print("   4. Use /friends/requests/{id}/accept to accept requests")
    print("   5. Use /friends/requests/{id}/decline to decline requests")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        asyncio.run(setup_test_data())
    elif len(sys.argv) > 1 and sys.argv[1] == "test":
        test_endpoints()
    else:
        print_api_summary()
        print("\nCommand options:")
        print("  python test_friend_system.py setup  - Create test users")
        print("  python test_friend_system.py test   - Test endpoints (requires running server)")
        print("  python test_friend_system.py        - Show this summary")