#!/usr/bin/env python3
"""
Test script to verify the friend system works end-to-end by creating test users and testing the flow.
"""
import asyncio
import sys
sys.path.append('.')
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import SessionLocal
from app.db import models
from sqlalchemy import select, delete
from app.core.security import get_password_hash

async def setup_test_users():
    """Create test users if they don't exist"""
    async with SessionLocal() as session:
        async with session.begin():
            # Check if users exist
            user1 = await session.execute(select(models.User).where(models.User.email == 'test1@gmail.com'))
            user2 = await session.execute(select(models.User).where(models.User.email == 'phiol.he@duke.edu'))
            
            u1 = user1.scalars().first()
            u2 = user2.scalars().first()
            
            if not u1:
                print("Creating test1@gmail.com...")
                u1 = models.User(
                    email="test1@gmail.com",
                    username="testuser1",
                    password_hash=get_password_hash("12345678")
                )
                session.add(u1)
                await session.flush()
                
                # Create profile
                profile1 = models.UserProfile(
                    user_id=u1.id,
                    avatar_url="https://api.dicebear.com/7.x/avataaars/svg?seed=test1"
                )
                session.add(profile1)
                print(f"Created test1@gmail.com with ID: {u1.id}")
            else:
                print(f"test1@gmail.com already exists with ID: {u1.id}")
            
            if not u2:
                print("Creating phiol.he@duke.edu...")
                u2 = models.User(
                    email="phiol.he@duke.edu",
                    username="phiolhe",
                    password_hash=get_password_hash("12345678")
                )
                session.add(u2)
                await session.flush()
                
                # Create profile
                profile2 = models.UserProfile(
                    user_id=u2.id,
                    avatar_url="https://api.dicebear.com/7.x/avataaars/svg?seed=phiol"
                )
                session.add(profile2)
                print(f"Created phiol.he@duke.edu with ID: {u2.id}")
            else:
                print(f"phiol.he@duke.edu already exists with ID: {u2.id}")
            
            # Clean up any existing friend relationships
            friendships = await session.execute(
                select(models.Friend).where(
                    (
                        (models.Friend.requester_id == u1.id) & 
                        (models.Friend.addressee_id == u2.id)
                    ) |
                    (
                        (models.Friend.requester_id == u2.id) & 
                        (models.Friend.addressee_id == u1.id)
                    )
                )
            )
            
            for f in friendships.scalars().all():
                await session.delete(f)
                print(f"Deleted existing friend relationship: {f.id}")
            
            print("\n✅ Test users ready!")
            print(f"   test1@gmail.com can now send friend request to phiol.he@duke.edu")

async def check_current_state():
    """Check the current state of friend relationships"""
    async with SessionLocal() as session:
        # Get both users
        user1 = await session.execute(select(models.User).where(models.User.email == 'test1@gmail.com'))
        user2 = await session.execute(select(models.User).where(models.User.email == 'phiol.he@duke.edu'))
        
        u1 = user1.scalars().first()
        u2 = user2.scalars().first()
        
        if not u1 or not u2:
            print("Users not found - run setup first")
            return
            
        print(f"\nCurrent State:")
        print(f"User 1: {u1.email} (ID: {u1.id[:8]}...)")
        print(f"User 2: {u2.email} (ID: {u2.id[:8]}...)")
        print()
        
        # Check friend relationships
        friendships = await session.execute(
            select(models.Friend).where(
                or_(
                    (models.Friend.requester_id == u1.id) & (models.Friend.addressee_id == u2.id),
                    (models.Friend.requester_id == u2.id) & (models.Friend.addressee_id == u1.id)
                )
            )
        )
        
        friend_records = friendships.scalars().all()
        
        if friend_records:
            print(f"❌ Found {len(friend_records)} existing relationship(s):")
            for f in friend_records:
                status_str = f.status.value if hasattr(f.status, 'value') else str(f.status)
                requester = u1.email if f.requester_id == u1.id else u2.email
                addressee = u2.email if f.addressee_id == u2.id else u1.email
                print(f"   - {requester} → {addressee}: {status_str}")
        else:
            print("✅ No existing relationships - clean slate!")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        asyncio.run(setup_test_users())
    elif len(sys.argv) > 1 and sys.argv[1] == "check":
        from sqlalchemy import or_
        asyncio.run(check_current_state())
    else:
        print("Usage: python3 test_with_frontend.py setup|check")
