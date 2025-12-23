# Backend Implementation Plan - Granular Verification Queue

## Objective
Update the `GET /proofs` endpoint to support the new Verification Queue requirements: showing "Friends' Approved" verifications (history) and "My Approved" verifications.

## Files to Modify
- `app/api/proofs.py`

## Detailed Changes

### 1. Update `list_proofs` in `app/api/proofs.py`

**Goal**: Modify the main query to return proofs that verify *either* the existing pending criteria *or* the new history criteria (approved by current user within last 48 hours).

**Logic**:
The current query filters for `status == pending`. We need to broaden this.

**Step-by-Step Implementation**:

1.  **Imports**: Ensure `timedelta` and `timezone` are imported from `datetime`.

2.  **Define 48-hour Cutoff**:
    ```python
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=48)
    ```

3.  **Create "Verified By Me Recently" Subquery**:
    Create a condition to find proofs where the current user is a verifier, the verification is approved, and it happened after the cutoff time.
    ```python
    verified_by_me_recently = select(models.ProofVerification).where(
        models.ProofVerification.proof_id == models.Proof.id,
        models.ProofVerification.verifier_id == current_user.id,
        models.ProofVerification.approved == True,
        models.ProofVerification.created_at >= cutoff_time
    ).exists()
    ```

4.  **Update `friends_proofs_stmt`**:
    Modify the `where` clause to accept the proof if it meets the *existing* pending criteria OR if it meets the *new* history criteria.

    *Existing Privacy Logic* (Preserve this):
    ```python
    privacy_check = or_(
        and_(
            models.Goal.privacy_setting == models.GoalPrivacy.friends,
            select(models.Friend).where(...).exists() # Existing friend check
        ),
        and_(
            models.Goal.privacy_setting == models.GoalPrivacy.select_friends,
            select(models.GoalAllowedViewer).where(...).exists() # Existing viewer check
        )
    )
    ```

    *New WHERE Clause*:
    ```python
    friends_proofs_stmt = select(models.Proof).join(
        models.Goal,
        models.Goal.id == models.Proof.goal_id
    ).where(
        and_(
            models.Proof.user_id != current_user.id, # Still never show my own proofs here
            or_(
                # Scenario A: Pending Verification (Old Logic)
                and_(
                    models.Proof.status == models.ProofStatus.pending,
                    privacy_check
                ),
                # Scenario B: Recently Approved by Me (New Logic)
                # Note: We implicitly assume if I verified it, I had permission, 
                # but good to keep privacy_check if strictly needed. 
                # However, if I verified it, I certainly saw it. 
                verified_by_me_recently
            )
        )
    )
    ```

5.  **Return Data**:
    The rest of the function (transformation to `ProofOut`) should remain largely the same, as `ProofOut` already contains `verifications` list. The frontend will use this list to determine which tab to show the proof in.
