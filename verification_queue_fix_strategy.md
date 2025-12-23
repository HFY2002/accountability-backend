# Verification Queue Bug Diagnosis and Fix Strategy

## Diagnosis
The issue where "Friends' Approved Verifications" and "My Approved Verifications" tabs are empty is caused by a **data contract mismatch** between the Frontend and the Backend.

### The Disconnect
The Frontend component `VerificationQueue.tsx` relies on specific field names to filter and display verification data. Specifically, it uses:
1. `v.timestamp` to check if a verification happened within the last 48 hours (via `isRecent` function).
2. `v.verifier_name` to display who verified the proof.
3. `proof.user_name` to display the proof owner's name.

However, the Backend API (`GET /proofs`) is currently returning:
1. `created_at` instead of `timestamp`.
2. `verifierName` instead of `verifier_name`.
3. `userName` instead of `user_name`.

### Why this breaks the UI
- **Empty Tabs**: The `isRecent(v.timestamp)` function returns `false` (or fails) because `v.timestamp` is `undefined`. Since the filter condition relies on this returning `true`, no proofs are passed to the "Approved" lists.
- **Missing Names**: `proof.user_name` and `v.verifier_name` are undefined, leading to blank names or fallback characters in the UI cards.

## Required Edits
To fix this, we need to align the Backend response schema with the Frontend's expectations. We will modify the Pydantic models in the backend.

### 1. File: `backend/app/schemas/proof.py`
We need to rename fields in `ProofVerificationOut` and `ProofOut` to match the frontend TypeScript interfaces.

**Edits:**
- Change `created_at` -> `timestamp`
- Change `verifierName` -> `verifier_name`
- Change `userName` -> `user_name`

```python
class ProofVerificationOut(BaseModel):
    id: UUID
    verifier_id: UUID
    verifier_name: Optional[str] = None  # Renamed from verifierName
    approved: bool
    comment: Optional[str] = None
    timestamp: datetime                  # Renamed from created_at

class ProofOut(BaseModel):
    # ... other fields ...
    user_name: Optional[str] = None      # Renamed from userName
    # ...
```

### 2. File: `backend/app/api/proofs.py`
We need to update the route handlers to populate these renamed fields correctly when creating the response objects.

**Edits in `list_proofs`, `get_proof_details`, and `verify_proof`:**

```python
# In constructing verif_out list:
verif_out.append(schemas.ProofVerificationOut(
    id=v.id,
    verifier_id=v.verifier_id,
    verifier_name=verifier.username if verifier else "Unknown", # Updated
    approved=v.approved,
    comment=v.comment,
    timestamp=v.created_at  # Updated mapping
))

# In constructing ProofOut:
proof_out = schemas.ProofOut(
    # ...
    user_name=user.username if user else "Unknown", # Updated
    # ...
)
```

## Conclusion
By standardizing these field names, the data will flow correctly into the frontend components. The `isRecent` check will find the `timestamp` it needs, populating the tabs, and the names will display correctly.
