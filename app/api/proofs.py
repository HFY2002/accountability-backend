from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from uuid import UUID
import uuid

from app.api import deps
from app.schemas import proof as schemas
from app.services.storage import storage_service
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
    # For now, get all pending proofs (can be refined later based on privacy settings)
    friends_proofs_stmt = select(models.Proof).where(
        and_(
            models.Proof.user_id != current_user.id,
            models.Proof.status == models.ProofStatus.pending
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
async def get_upload_url(filename: str, content_type: str):
    """
    Get a presigned URL to upload a file directly to MinIO/S3.
    """
    ext = filename.split(".")[-1]
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

    # 2. Determine verification requirements based on privacy
    required = 1 
    if goal.privacy_setting == models.GoalPrivacy.select_friends:
        # Future logic: Count 'can_verify' allowed viewers
        pass

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

    # 4. Trigger Notifications (Logic skipped for brevity)
    
    return db_proof

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