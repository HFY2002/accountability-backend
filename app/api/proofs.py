from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from uuid import UUID
import uuid
import re
from datetime import datetime, timedelta, timezone

from app.api import deps
from app.schemas import proof as schemas
from app.services.storage import storage_service
from app.services.notification import create_notification
from app.db import models

router = APIRouter()

# NEW: Background task to expire old proofs
async def expire_old_proofs(db: AsyncSession):
    """Expire proofs that are past their 72-hour verification window"""
    expiry_time = datetime.now(timezone.utc) - timedelta(hours=72)
    
    # Find pending proofs past expiry
    expired_stmt = select(models.Proof).where(
        models.Proof.status == models.ProofStatus.pending,
        models.Proof.verification_expires_at < datetime.now(timezone.utc)
    )
    result = await db.execute(expired_stmt)
    expired_proofs = result.scalars().all()
    
    for proof in expired_proofs:
        proof.status = models.ProofStatus.rejected
        
        # Create expiry notification for the uploader
        await create_notification(
            db,
            recipient_id=proof.user_id,
            type=models.NotificationType.proof_expired,
            message=f"Your proof for '{proof.goal.title}' has expired without sufficient verifications",
            actor_id=proof.user_id,  # System notification
            goal_id=proof.goal_id,
            proof_id=proof.id
        )
    
    await db.commit()

# NEW: Check if user can verify a proof based on privacy settings
async def can_user_verify_proof(
    db: AsyncSession,
    user_id: UUID,
    proof: models.Proof
) -> bool:
    """Check if user has permission to verify this proof based on privacy settings"""
    
    # Cannot verify your own proof
    if proof.user_id == user_id:
        return False
    
    # Get the goal
    goal_stmt = select(models.Goal).where(models.Goal.id == proof.goal_id)
    goal_result = await db.execute(goal_stmt)
    goal = goal_result.scalars().first()
    
    if not goal:
        return False
    
    # Check privacy setting
    if goal.privacy_setting == models.GoalPrivacy.select_friends:
        # Check if user is in allowed viewers list
        viewer_stmt = select(models.GoalAllowedViewer).where(
            models.GoalAllowedViewer.goal_id == goal.id,
            models.GoalAllowedViewer.user_id == user_id,
            models.GoalAllowedViewer.can_verify == True
        )
        viewer_result = await db.execute(viewer_stmt)
        return viewer_result.scalars().first() is not None
        
    elif goal.privacy_setting == models.GoalPrivacy.friends:
        # Check if users are friends
        friend_stmt = select(models.Friend).where(
            or_(
                and_(
                    models.Friend.requester_id == user_id,
                    models.Friend.addressee_id == proof.user_id,
                    models.Friend.status == models.FriendStatus.accepted
                ),
                and_(
                    models.Friend.requester_id == proof.user_id,
                    models.Friend.addressee_id == user_id,
                    models.Friend.status == models.FriendStatus.accepted
                )
            )
        )
        friend_result = await db.execute(friend_stmt)
        return friend_result.scalars().first() is not None
    
    return False  # Private goals cannot be verified by others

@router.get("", response_model=list[schemas.ProofOut])
async def list_proofs(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    List all proofs that the current user can see/verify:
    - Proofs submitted by the user (their pending proofs)
    - Proofs from friends that are pending verification
    """
    # Expire old proofs first
    background_tasks.add_task(expire_old_proofs, db)
    
    # Get proofs submitted by current user
    user_proofs_stmt = select(models.Proof).where(
        models.Proof.user_id == current_user.id
    )
    
    # Define 48-hour cutoff for recently approved proofs
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=48)
    
    # Create "Verified By Me Recently" Subquery
    verified_by_me_recently = select(models.ProofVerification).where(
        models.ProofVerification.proof_id == models.Proof.id,
        models.ProofVerification.verifier_id == current_user.id,
        models.ProofVerification.approved == True,
        models.ProofVerification.created_at >= cutoff_time
    ).exists()
    
    # Define privacy check (existing logic)
    privacy_check = or_(
        and_(
            models.Goal.privacy_setting == models.GoalPrivacy.friends,
            select(models.Friend).where(
                or_(
                    and_(
                        models.Friend.requester_id == current_user.id,
                        models.Friend.addressee_id == models.Proof.user_id,
                        models.Friend.status == models.FriendStatus.accepted
                    ),
                    and_(
                        models.Friend.addressee_id == current_user.id,
                        models.Friend.requester_id == models.Proof.user_id,
                        models.Friend.status == models.FriendStatus.accepted
                    )
                )
            ).exists()
        ),
        and_(
            models.Goal.privacy_setting == models.GoalPrivacy.select_friends,
            select(models.GoalAllowedViewer).where(
                models.GoalAllowedViewer.goal_id == models.Goal.id,
                models.GoalAllowedViewer.user_id == current_user.id,
                models.GoalAllowedViewer.can_verify == True
            ).exists()
        )
    )
    
    # Get proofs from friends - both pending and recently approved by me
    friends_proofs_stmt = select(models.Proof).join(
        models.Goal,
        models.Goal.id == models.Proof.goal_id
    ).where(
        and_(
            models.Proof.user_id != current_user.id,  # Still never show my own proofs here
            or_(
                # Scenario A: Pending Verification (Old Logic)
                and_(
                    models.Proof.status == models.ProofStatus.pending,
                    privacy_check
                ),
                # Scenario B: Recently Approved by Me (New Logic)
                verified_by_me_recently
            )
        )
    )
    
    # Execute both queries
    user_proofs_result = await db.execute(user_proofs_stmt)
    friends_proofs_result = await db.execute(friends_proofs_stmt)
    
    user_proofs = user_proofs_result.scalars().all(); print(f"DEBUG Proof Listing: User {current_user.id} querying proofs...")
    friends_proofs = friends_proofs_result.scalars().all(); print(f"DEBUG Proof Listing: Found {len(user_proofs)} user proofs, {len(friends_proofs)} friend proofs")

    
    # Combine all proofs
    all_proofs = list(user_proofs) + list(friends_proofs)
    
    # Transform to include additional frontend-required fields
    result = []
    for proof in all_proofs:
        # Get the user who submitted the proof
        user_stmt = select(models.User).where(models.User.id == proof.user_id)
        user_result = await db.execute(user_stmt)
        user = user_result.scalars().first()
        
        # Get the goal details
        goal_stmt = select(models.Goal).where(models.Goal.id == proof.goal_id)
        goal_result = await db.execute(goal_stmt)
        goal = goal_result.scalars().first()
        
        # Get milestone details if milestone_id exists
        milestone_title = None
        milestone_description = None
        if proof.milestone_id:
            milestone_stmt = select(models.Milestone).where(models.Milestone.id == proof.milestone_id)
            milestone_result = await db.execute(milestone_stmt)
            milestone = milestone_result.scalars().first()
            if milestone:
                milestone_title = milestone.title
                milestone_description = milestone.description
        
        # Get verification details
        verif_stmt = select(models.ProofVerification).where(
            models.ProofVerification.proof_id == proof.id
        )
        verif_result = await db.execute(verif_stmt)
        verifications = verif_result.scalars().all()
        
        # Check if current user can verify this proof
        can_verify = False
        if proof.user_id != current_user.id:
            can_verify = await can_user_verify_proof(db, current_user.id, proof)
        
        # Transform verifications to include verifier names
        verif_out = []
        for v in verifications:
            verifier_stmt = select(models.User).where(models.User.id == v.verifier_id)
            verifier_result = await db.execute(verifier_stmt)
            verifier = verifier_result.scalars().first()
            
            verif_out.append(schemas.ProofVerificationOut(
                id=v.id,
                verifier_id=v.verifier_id,
                verifier_name=verifier.username if verifier else "Unknown",
                approved=v.approved,
                comment=v.comment,
                timestamp=v.created_at
            ))
        
        # Create the proof output with all required fields
        proof_out = schemas.ProofOut(
            id=proof.id,
            goal_id=proof.goal_id,
            milestone_id=proof.milestone_id,
            user_id=proof.user_id,
            user_name=user.username if user else "Unknown",
            image_url=proof.image_url,
            caption=proof.caption,
            status=proof.status,
            requiredVerifications=proof.required_verifications,
            uploadedAt=proof.uploaded_at,  # FIXED: Uses uploaded_at field
            verificationExpiresAt=proof.verification_expires_at,  # NEW: Expiry time
            verifications=verif_out,
            goalTitle=goal.title if goal else "Unknown Goal",
            milestoneTitle=milestone_title,
            milestoneDescription=milestone_description,
            canVerify=can_verify  # NEW: Permission flag
        )
        result.append(proof_out)
    
    return result

@router.get("/{proof_id}", response_model=schemas.ProofOut)
async def get_proof_details(
    proof_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    Get detailed information about a single proof.
    Includes milestone details and full verification information.
    Enhanced with access control checks.
    """
    # Fetch the proof
    proof_stmt = select(models.Proof).where(models.Proof.id == proof_id)
    proof_result = await db.execute(proof_stmt)
    proof = proof_result.scalars().first()
    
    if not proof:
        raise HTTPException(status_code=404, detail="Proof not found")
    
    # Check if user has permission to view this proof
    # User can view if they submitted it OR if they're an allowed verifier
    if proof.user_id != current_user.id:
        # Check if user can verify (which also means they can view)
        if not await can_user_verify_proof(db, current_user.id, proof):
            raise HTTPException(status_code=403, detail="You don't have permission to view this proof")
    
    # Check if proof has expired
    if proof.verification_expires_at and proof.verification_expires_at < datetime.now(timezone.utc):
        if proof.status == models.ProofStatus.pending:
            proof.status = models.ProofStatus.rejected
            await db.commit()
            await db.refresh(proof)
    
    # Get all related details
    user_stmt = select(models.User).where(models.User.id == proof.user_id)
    user_result = await db.execute(user_stmt)
    user = user_result.scalars().first()
    
    goal_stmt = select(models.Goal).where(models.Goal.id == proof.goal_id)
    goal_result = await db.execute(goal_stmt)
    goal = goal_result.scalars().first()
    
    # Get milestone details
    milestone_title = None
    milestone_description = None
    if proof.milestone_id:
        milestone_stmt = select(models.Milestone).where(models.Milestone.id == proof.milestone_id)
        milestone_result = await db.execute(milestone_stmt)
        milestone = milestone_result.scalars().first()
        if milestone:
            milestone_title = milestone.title
            milestone_description = milestone.description
    
    # Get verification details
    verif_stmt = select(models.ProofVerification).where(
        models.ProofVerification.proof_id == proof.id
    )
    verif_result = await db.execute(verif_stmt)
    verifications = verif_result.scalars().all()
    
    # Check if current user can verify
    can_verify = False
    if proof.user_id != current_user.id:
        can_verify = await can_user_verify_proof(db, current_user.id, proof)
    
    # Transform verifications
    verif_out = []
    for v in verifications:
        verifier_stmt = select(models.User).where(models.User.id == v.verifier_id)
        verifier_result = await db.execute(verifier_stmt)
        verifier = verifier_result.scalars().first()
        
        verif_out.append(schemas.ProofVerificationOut(
            id=v.id,
            verifier_id=v.verifier_id,
            verifier_name=verifier.username if verifier else "Unknown",
            approved=v.approved,
            comment=v.comment,
            timestamp=v.created_at
        ))
    
    return schemas.ProofOut(
        id=proof.id,
        goal_id=proof.goal_id,
        milestone_id=proof.milestone_id,
        user_id=proof.user_id,
        user_name=user.username if user else "Unknown", # Renamed from userName
        image_url=proof.image_url,
        caption=proof.caption,
        status=proof.status,
        requiredVerifications=proof.required_verifications,
        uploadedAt=proof.uploaded_at,
        verificationExpiresAt=proof.verification_expires_at,
        verifications=verif_out,
        goalTitle=goal.title if goal else "Unknown Goal",
        milestoneTitle=milestone_title,
        milestoneDescription=milestone_description,
        canVerify=can_verify
    )

@router.get("/storage/upload-url")
async def get_upload_url(
    filename: str, 
    content_type: str,
    current_user: models.User = Depends(deps.get_current_user)
):
    """
    Get a presigned URL to upload a file directly to MinIO/S3.
    Validates file type and size limits.
    """
    # Validate file type - accept only images
    allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'heic', 'heif'}
    allowed_content_types = {
        'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 
        'image/webp', 'image/heic', 'image/heif', 'image/heif-sequence'
    }
    
    ext = filename.split(".")[-1].lower()
    
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}"
        )
    
    if content_type and content_type.lower() not in allowed_content_types:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid content type. Allowed types: {', '.join(allowed_content_types)}"
        )
    
    # Generate random filename
    storage_key = f"{uuid.uuid4()}.{ext}"
    
    url = storage_service.generate_presigned_put(storage_key, content_type)
    public_url = storage_service.get_public_url(storage_key)
    
    return {"upload_url": url, "public_url": public_url, "file_path": storage_key}

@router.post("", response_model=schemas.ProofOut)
async def create_proof(
    proof_in: schemas.ProofCreateIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    # 1. Validate Goal
    goal_stmt = select(models.Goal).where(models.Goal.id == proof_in.goal_id)
    res = await db.execute(goal_stmt)
    goal = res.scalars().first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    # 2. Validate milestone (if provided) belongs to this goal
    if proof_in.milestone_id:
        milestone_stmt = select(models.Milestone).where(
            models.Milestone.id == proof_in.milestone_id,
            models.Milestone.goal_id == proof_in.goal_id
        )
        milestone_res = await db.execute(milestone_stmt)
        if not milestone_res.scalars().first():
            raise HTTPException(status_code=400, detail="Milestone does not belong to the specified goal")

    # 3. Determine verification requirements based on privacy
    from sqlalchemy import func
    
    required = 1 
    if goal.privacy_setting == models.GoalPrivacy.select_friends:
        # Count specific allowed viewers
        viewer_count_stmt = select(func.count()).where(
            models.GoalAllowedViewer.goal_id == goal.id,
            models.GoalAllowedViewer.can_verify == True
        )
        viewer_count_result = await db.execute(viewer_count_stmt)
        required = viewer_count_result.scalar() or 1
    elif goal.privacy_setting == models.GoalPrivacy.friends:
        # For 'friends' privacy, count all accepted friends
        friend_count_stmt = select(func.count()).where(
            or_(
                models.Friend.requester_id == current_user.id,
                models.Friend.addressee_id == current_user.id
            ),
            models.Friend.status == models.FriendStatus.accepted
        )
        friend_count_result = await db.execute(friend_count_stmt)
        required = friend_count_result.scalar() or 1
    else:
        # For private goals, only 1 verification needed (from self or default)
        required = 1

    # 4. Save Proof (image_url generated from key)
    # NEW: Set 72-hour expiry time
    verification_expires_at = datetime.now(timezone.utc) + timedelta(hours=72)
    
    db_proof = models.Proof(
        goal_id=proof_in.goal_id,
        milestone_id=proof_in.milestone_id,
        user_id=current_user.id,
        image_url=storage_service.get_public_url(proof_in.storage_key),
        caption=proof_in.caption,
        status=models.ProofStatus.pending,
        required_verifications=required,
        verification_expires_at=verification_expires_at
    )
    db.add(db_proof)
    await db.flush()  # Flush to get the proof ID

    # 5. Trigger Notifications for verifiers based on privacy settings
    if goal.privacy_setting == models.GoalPrivacy.select_friends:
        # Get specific allowed viewers
        viewers_stmt = select(models.GoalAllowedViewer).where(
            models.GoalAllowedViewer.goal_id == goal.id,
            models.GoalAllowedViewer.can_verify == True
        )
        viewers_result = await db.execute(viewers_stmt)
        viewers = viewers_result.scalars().all()
        print(f"DEBUG Proof Creation: Goal {goal.id} has {len(viewers)} allowed viewers for notifications")
        
        for viewer in viewers:
            await create_notification(
                db,
                recipient_id=viewer.user_id,
                type=models.NotificationType.proof_submission,
                message=f"{current_user.username} submitted proof for milestone in '{goal.title}'",
                actor_id=current_user.id,
                goal_id=goal.id,
                proof_id=db_proof.id
            )
    
    elif goal.privacy_setting == models.GoalPrivacy.friends:
        # Get all accepted friends
        friends_stmt = select(models.Friend).where(
            or_(
                models.Friend.requester_id == current_user.id,
                models.Friend.addressee_id == current_user.id
            ),
            models.Friend.status == models.FriendStatus.accepted
        )
        friends_result = await db.execute(friends_stmt)
        friendships = friends_result.scalars().all()
        
        # Extract friend IDs and send notifications
        for friendship in friendships:
            friend_id = (friendship.addressee_id if friendship.requester_id == current_user.id 
                        else friendship.requester_id)
            
            await create_notification(
                db,
                recipient_id=friend_id,
                type=models.NotificationType.proof_submission,
                message=f"{current_user.username} submitted proof for milestone in '{goal.title}'",
                actor_id=current_user.id,
                goal_id=goal.id,
                proof_id=db_proof.id
            )
    
    await db.commit()
    await db.refresh(db_proof)

    # 6. Get milestone details for response
    milestone_title = None
    milestone_description = None
    if db_proof.milestone_id:
        milestone_stmt = select(models.Milestone).where(models.Milestone.id == db_proof.milestone_id)
        milestone_result = await db.execute(milestone_stmt)
        milestone = milestone_result.scalars().first()
        if milestone:
            milestone_title = milestone.title
            milestone_description = milestone.description

    # 7. Return properly formatted response
    return schemas.ProofOut(
        id=db_proof.id,
        goal_id=db_proof.goal_id,
        milestone_id=db_proof.milestone_id,
        user_id=db_proof.user_id,
        userName=current_user.username,
        image_url=db_proof.image_url,
        caption=db_proof.caption,
        status=db_proof.status,
        requiredVerifications=db_proof.required_verifications,
        uploadedAt=db_proof.uploaded_at,
        verificationExpiresAt=db_proof.verification_expires_at,  # NEW: Include expiry time
        verifications=[],  # New proof has no verifications yet
        goalTitle=goal.title if goal else "Unknown Goal",
        milestoneTitle=milestone_title,
        milestoneDescription=milestone_description,
        canVerify=False  # User cannot verify their own proof
    )

@router.post("/{proof_id}/verifications")
async def verify_proof(
    proof_id: UUID,
    verification: schemas.ProofVerificationCreateIn,
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    # 1. Fetch Proof
    proof_stmt = select(models.Proof).where(models.Proof.id == proof_id)
    res = await db.execute(proof_stmt)
    proof = res.scalars().first()
    
    if not proof:
        raise HTTPException(status_code=404, detail="Proof not found")
    
    # NEW: Check if proof has expired
    if proof.verification_expires_at and proof.verification_expires_at < datetime.now(timezone.utc):
        if proof.status == models.ProofStatus.pending:
            proof.status = models.ProofStatus.rejected
            await db.commit()
            await db.refresh(proof)
        raise HTTPException(status_code=400, detail="This proof has expired and can no longer be verified")
    
    # NEW: Enhanced access control check
    if not await can_user_verify_proof(db, current_user.id, proof):
        if proof.user_id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot verify your own proof")
        else:
            raise HTTPException(status_code=403, detail="You don't have permission to verify this proof")
    
    # 2. Check if user has already verified this proof
    existing_verif_stmt = select(models.ProofVerification).where(
        models.ProofVerification.proof_id == proof_id,
        models.ProofVerification.verifier_id == current_user.id
    )
    existing_result = await db.execute(existing_verif_stmt)
    if existing_result.scalars().first():
        raise HTTPException(status_code=400, detail="You have already verified this proof")

    # 3. Record Verification
    verif = models.ProofVerification(
        proof_id=proof_id,
        verifier_id=current_user.id,
        approved=verification.approved,
        comment=verification.comment
    )
    db.add(verif)
    
    # 3.5 Fetch the goal for the notification message
    goal_stmt = select(models.Goal).where(models.Goal.id == proof.goal_id)
    goal_result = await db.execute(goal_stmt)
    goal = goal_result.scalars().first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    # 4. Check if threshold is met to approve the proof
    if verification.approved:
        # Count approved verifications
        count_stmt = select(func.count()).where(
            models.ProofVerification.proof_id == proof_id,
            models.ProofVerification.approved == True
        )
        count_result = await db.execute(count_stmt)
        approved_count = count_result.scalar()
        
        # If threshold met, approve the proof
        if approved_count >= proof.required_verifications:
            proof.status = models.ProofStatus.approved
            
            # Mark milestone as completed if this proof is for a milestone
            if proof.milestone_id:
                milestone_stmt = select(models.Milestone).where(
                    models.Milestone.id == proof.milestone_id
                )
                milestone_result = await db.execute(milestone_stmt)
                milestone = milestone_result.scalars().first()
                
                if milestone:
                    milestone.completed = True
                    milestone.completed_at = func.now()
    else:
        # If any verifier rejects, mark proof as rejected
        proof.status = models.ProofStatus.rejected

    # 5. Create verification notification
    await create_notification(
        db,
        recipient_id=proof.user_id,
        type=models.NotificationType.proof_verified,
        message=f"{current_user.username} {'approved' if verification.approved else 'rejected'} your proof for '{goal.title}'",
        actor_id=current_user.id,
        goal_id=proof.goal_id,
        proof_id=proof.id
    )
    
    await db.commit()
    
    # 6. Return the updated proof with all details
    # Fetch updated proof with all verifications
    verif_stmt = select(models.ProofVerification).where(
        models.ProofVerification.proof_id == proof_id
    )
    verif_result = await db.execute(verif_stmt)
    verifications = verif_result.scalars().all()
    
    # Get milestone details
    milestone_title = None
    milestone_description = None
    if proof.milestone_id:
        milestone_stmt = select(models.Milestone).where(models.Milestone.id == proof.milestone_id)
        milestone_result = await db.execute(milestone_stmt)
        milestone = milestone_result.scalars().first()
        if milestone:
            milestone_title = milestone.title
            milestone_description = milestone.description
    
    # Transform verifications
    verif_out = []
    for v in verifications:
        verifier_stmt = select(models.User).where(models.User.id == v.verifier_id)
        verifier_result = await db.execute(verifier_stmt)
        verifier = verifier_result.scalars().first()
        
        verif_out.append(schemas.ProofVerificationOut(
            id=v.id,
            verifier_id=v.verifier_id,
            verifier_name=verifier.username if verifier else "Unknown",
            approved=v.approved,
            comment=v.comment,
            timestamp=v.created_at
        ))
    
    user_stmt = select(models.User).where(models.User.id == proof.user_id)
    user_result = await db.execute(user_stmt)
    user = user_result.scalars().first()
    
    goal_stmt = select(models.Goal).where(models.Goal.id == proof.goal_id)
    goal_result = await db.execute(goal_stmt)
    goal = goal_result.scalars().first()
    
    return schemas.ProofOut(
        id=proof.id,
        goal_id=proof.goal_id,
        milestone_id=proof.milestone_id,
        user_id=proof.user_id,
        user_name=user.username if user else "Unknown", # Renamed from userName
        image_url=proof.image_url,
        caption=proof.caption,
        status=proof.status,
        requiredVerifications=proof.required_verifications,
        uploadedAt=proof.uploaded_at,
        verificationExpiresAt=proof.verification_expires_at,
        verifications=verif_out,
        goalTitle=goal.title if goal else "Unknown Goal",
        milestoneTitle=milestone_title,
        milestoneDescription=milestone_description,
        canVerify=False  # After verification, user can no longer verify
    )