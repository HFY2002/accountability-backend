#!/usr/bin/env python3
"""
Reproduction script for the verification queue bug.
This script demonstrates the bug where allowed viewers cannot see proofs for verification.
"""

import asyncio
import sys
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from app.db.models import (
    User, Goal, Milestone, GoalPrivacy, FriendStatus, Friend, 
    GoalAllowedViewer, Proof, ProofStatus
)
from app.db.session import SessionLocal as async_session

async def reproduce_bug():
    """Reproduce the verification queue bug"""
    
    print("=" * 80)
    print("REPRODUCING VERIFICATION QUEUE BUG")
    print("=" * 80)
    
    async with async_session() as db:
        try:
            # Create test data
            print("\n1. Creating test users...")
            user_a = User(
                email="user_a@example.com",
                username="user_a",
                password_hash="hash_a",
                is_active=True
            )
            user_b = User(
                email="user_b@example.com",
                username="user_b", 
                password_hash="hash_b",
                is_active=True
            )
            db.add(user_a)
            db.add(user_b)
            await db.flush()
            print(f"   ✓ User A ID: {user_a.id}")
            print(f"   ✓ User B ID: {user_b.id}")
            
            # Create friendship
            print("\n2. Creating friendship...")
            friendship = Friend(
                requester_id=user_a.id,
                addressee_id=user_b.id,
                status=FriendStatus.accepted
            )
            db.add(friendship)
            await db.flush()
            print("   ✓ Friendship created")
            
            # Create goal with select_friends privacy
            print("\n3. Creating goal with select_friends privacy...")
            goal = Goal(
                user_id=user_a.id,
                title="Fitness Challenge",
                description="30 day fitness challenge",
                start_date="2024-01-01",
                deadline="2024-02-01",
                privacy_setting=GoalPrivacy.select_friends,
                milestone_type="flexible",
                milestone_interval_days=7,
                status="active"
            )
            db.add(goal)
            await db.flush()
            print(f"   ✓ Goal created: {goal.id}")
            
            # Add user_b as allowed viewer
            print("\n4. Adding User B as allowed viewer...")
            viewer = GoalAllowedViewer(
                goal_id=goal.id,
                user_id=user_b.id,
                can_verify=True
            )
            db.add(viewer)
            await db.flush()
            print("   ✓ User B added as allowed viewer")
            
            # Create milestone
            print("\n5. Creating milestone...")
            milestone = Milestone(
                goal_id=goal.id,
                title="Week 1 Milestone",
                description="Complete first week",
                order_index=0,
                batch_number=1,
                is_flexible=True,
                due_date="2024-01-08"
            )
            db.add(milestone)
            await db.flush()
            print(f"   ✓ Milestone created: {milestone.id}")
            
            # Submit proof (as User A)
            print("\n6. Submitting proof (as User A)...")
            proof = Proof(
                goal_id=goal.id,
                milestone_id=milestone.id,
                user_id=user_a.id,
                image_url="http://minio.example.com/proof.jpg",
                caption="Completed my first week!",
                status=ProofStatus.pending,
                required_verifications=1  # Only User B needs to verify
            )
            db.add(proof)
            await db.flush()
            print(f"   ✓ Proof submitted: {proof.id}")
            print(f"   ✓ Required verifications: {proof.required_verifications}")
            
            await db.commit()
            
            # Now test the FLAWED query (current implementation)
            print("\n7. Testing CURRENT (flawed) query logic...")
            print("   (This query simulates what happens when User B opens /api/v1/proofs)")
            
            # This is the EXACT query from the current codebase
            friends_proofs_stmt = select(Proof).join(
                Goal,
                Goal.id == Proof.goal_id
            ).join(
                GoalAllowedViewer,
                GoalAllowedViewer.goal_id == Goal.id,
                isouter=True  # This is the PROBLEM!
            ).where(
                and_(
                    Proof.user_id != user_b.id,  # Not submitted by User B
                    Proof.status == ProofStatus.pending,
                    or_(
                        # Goal is set to 'friends' (no specific restrictions)
                        Goal.privacy_setting == GoalPrivacy.friends,
                        # User is in the allowed viewers list
                        and_(
                            Goal.privacy_setting == GoalPrivacy.select_friends,
                            GoalAllowedViewer.user_id == user_b.id,
                            GoalAllowedViewer.can_verify == True
                        )
                    )
                )
            )
            
            result = await db.execute(friends_proofs_stmt)
            flawed_proofs = result.scalars().all()
            
            print(f"   ❌ Current query returned {len(flawed_proofs)} proofs")
            for p in flawed_proofs:
                print(f"      - Proof {p.id} for goal {p.goal_id}")
            
            if len(flawed_proofs) == 0:
                print("   ❌ BUG CONFIRMED: User B cannot see User A's proof!")
            
            # Now test the FIXED query (proposed solution)
            print("\n8. Testing FIXED query logic...")
            print("   (Using EXISTS subquery instead of flawed JOIN)")
            
            fixed_proofs_stmt = select(Proof).where(
                and_(
                    Proof.user_id != user_b.id,
                    Proof.status == ProofStatus.pending,
                    Goal.privacy_setting == GoalPrivacy.select_friends,
                    # EXPLICIT check that user is in allowed viewers
                    select(GoalAllowedViewer).where(
                        GoalAllowedViewer.goal_id == Goal.id,
                        GoalAllowedViewer.user_id == user_b.id,
                        GoalAllowedViewer.can_verify == True
                    ).exists()
                )
            )
            
            result = await db.execute(fixed_proofs_stmt)
            fixed_proofs = result.scalars().all()
            
            print(f"   ✅ Fixed query returned {len(fixed_proofs)} proofs")
            for p in fixed_proofs:
                print(f"      - Proof {p.id} for goal {p.goal_id}")
            
            if len(fixed_proofs) >= 1:
                print("   ✅ FIXED: User B can now see User A's proof for verification!")
            
            # Summary
            print("\n" + "=" * 80)
            print("BUG REPRODUCTION COMPLETE")
            print("=" * 80)
            print()
            if len(flawed_proofs) == 0 and len(fixed_proofs) >= 1:
                print("✅ BUG CONFIRMED AND VALIDATED")
                print()
                print("Root Cause:")
                print("- The isouter=True (LEFT JOIN) on GoalAllowedViewer")
                print("- Prevents proper filtering for select_friends privacy")
                print("- SQL NULL logic causes 'unknown' instead of 'false'")
                print()
                print("Impact:")
                print("- Allowed viewers cannot see proofs for verification")
                print("- Goal progress is blocked")
                print("- Notifications are sent but verification queue is empty")
                return True
            else:
                print("❌ Bug not reproduced - query logic may have changed")
                return False
                
        except Exception as e:
            print(f"❌ Error during reproduction: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Cleanup
            print("\n9. Cleaning up test data...")
            await db.execute(
                select(Proof).where(Proof.id == proof.id)
            )
            await db.delete(proof)
            await db.execute(
                select(Milestone).where(Milestone.id == milestone.id)
            )
            await db.delete(milestone)
            await db.execute(
                select(GoalAllowedViewer).where(GoalAllowedViewer.goal_id == goal.id)
            )
            viewer_to_delete = await db.execute(
                select(GoalAllowedViewer).where(GoalAllowedViewer.goal_id == goal.id)
            )
            for v in viewer_to_delete.scalars().all():
                await db.delete(v)
            await db.delete(goal)
            await db.execute(
                select(Friend).where(Friend.id == friendship.id)
            )
            await db.delete(friendship)
            await db.execute(
                select(User).where(User.id == user_a.id)
            )
            await db.delete(user_a)
            await db.execute(
                select(User).where(User.id == user_b.id)
            )
            await db.delete(user_b)
            await db.commit()
            print("   ✓ Cleanup complete")

if __name__ == "__main__":
    result = asyncio.run(reproduce_bug())
    sys.exit(0 if result else 1)