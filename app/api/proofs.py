from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from uuid import UUID
import uuid
import re

from app.api import deps
from app.schemas import proof as schemas
from app.services.storage import storage_service
from app.services.notification import create_notification
from app.db import models

router = APIRouter()

@router.get("", response_model=list[schemas.ProofOut])
async def list_proofs(
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_user),
):
    """
    List all proofs that the current user can see/verify:
    - Proofs submitted by the user (their pending proofs)
    - Proofs from friends that are pending verification
    """
    # Get proofs submitted by current user
    user_proofs_stmt = select(models.Proof).where(
        models.Proof.user_id == current_user.id
    )
    
    # Get proofs from friends that are pending and need verification
    # Filter based on privacy settings - only show proofs where user is an allowed viewer
    friends_proofs_stmt = select(models.Proof).join(
        models.Goal,
        models.Goal.id == models.Proof.goal_id
    ).join(
        models.GoalAllowedViewer,
        models.GoalAllowedViewer.goal_id == models.Goal.id,
        isouter=True  # Left join for goals without specific viewers
    ).where(
        and_(
            models.Proof.user_id != current_user.id,
            models.Proof.status == models.ProofStatus.pending,
            or_(
                # Goal is set to 'friends' (no specific restrictions)
                models.Goal.privacy_setting == models.GoalPrivacy.friends,
                # User is in the allowed viewers list
                and_(
                    models.Goal.privacy_setting == models.GoalPrivacy.select_friends,
                    models.GoalAllowedViewer.user_id == current_user.id,
                    models.GoalAllowedViewer.can_verify == True
                )
            )
        )
    )
    
    # Execute both queries
    user_proofs_result = await db.execute(user_proofs_stmt)
    friends_proofs_result = await db.execute(friends_proofs_stmt)
    
    user_proofs = user_proofs_result.scalars().all()
    friends_proofs = friends_proofs_result.scalars().all()
    
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
        
        # Get verification details
        verif_stmt = select(models.ProofVerification).where(
            models.ProofVerification.proof_id == proof.id
        )
        verif_result = await db.execute(verif_stmt)
        verifications = verif_result.scalars().all()
        
        # Transform verifications to include verifier names
        verif_out = []
        for v in verifications:
            verifier_stmt = select(models.User).where(models.User.id == v.verifier_id)
            verifier_result = await db.execute(verifier_stmt)
            verifier = verifier_result.scalars().first()
            
            verif_out.append(schemas.ProofVerificationOut(
                id=v.id,
                verifier_id=v.verifier_id,
                verifierName=verifier.username if verifier else "Unknown",
                approved=v.approved,
                comment=v.comment,
                created_at=v.created_at
            ))
        
        # Create the proof output with all required fields
        proof_out = schemas.ProofOut(
            id=proof.id,
            goal_id=proof.goal_id,
            milestone_id=proof.milestone_id,
            user_id=proof.user_id,
            userName=user.username if user else "Unknown",
            image_url=proof.image_url,
            caption=proof.caption,
            status=proof.status,
            requiredVerifications=proof.required_verifications,
            uploadedAt=proof.created_at,
            verifications=verif_out,
            goalTitle=goal.title if goal else "Unknown Goal"
        )
        result.append(proof_out)
    
    return result

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

    # 3. Save Proof (image_url generated from key)
    db_proof = models.Proof(
        goal_id=proof_in.goal_id,
        milestone_id=proof_in.milestone_id,
        user_id=current_user.id,
        image_url=storage_service.get_public_url(proof_in.storage_key),
        caption=proof_in.caption,
        status=models.ProofStatus.pending,
        required_verifications=required
    )
    db.add(db_proof)
    await db.commit()
    await db.refresh(db_proof)

    # 4. Trigger Notifications for verifiers based on privacy settings
    if goal.privacy_setting == models.GoalPrivacy.select_friends:
        # Get specific allowed viewers
        viewers_stmt = select(models.GoalAllowedViewer).where(
            models.GoalAllowedViewer.goal_id == goal.id,
            models.GoalAllowedViewer.can_verify == True
        )
        viewers_result = await db.execute(viewers_stmt)
        viewers = viewers_result.scalars().all()
        
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
    
    # 5. Return properly formatted response
    # The ProofOut schema expects these fields, so construct it manually
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
        uploadedAt=db_proof.created_at,
        verifications=[],  # New proof has no verifications yet
        goalTitle=goal.title if goal else "Unknown Goal"
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
    
    if proof.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot verify your own proof")

    # 2. Record Verification
    verif = models.ProofVerification(
        proof_id=proof_id,
        verifier_id=current_user.id,
        approved=verification.approved,
        comment=verification.comment
    )
    db.add(verif)
    
    # 3. Logic: Check if threshold met to approve proof entirely
    # if verification.approved and (count >= proof.required_verifications):
    #     proof.status = models.ProofStatus.approved
    
    await db.commit()
    return proof