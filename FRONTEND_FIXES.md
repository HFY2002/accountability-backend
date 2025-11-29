# Frontend Fixes Implementation Guide

## 1. TypeScript Type Updates

### File: /frontend/src/types/index.ts

Replace the existing `Proof` and `Verification` interfaces with:

```typescript
export interface Proof {
  id: string;
  goal_id: string;
  milestone_id?: string;
  user_id: string;
  userName?: string;
  image_url?: string;
  caption: string;
  uploadedAt?: string;
  verifications: Verification[];
  requiredVerifications: number;
  status: 'pending' | 'approved' | 'rejected';
  goalTitle?: string;
  milestoneTitle?: string;
  milestoneDescription?: string;
}

export interface Verification {
  id: string;
  verifier_id: string;
  verifierName?: string;
  approved: boolean;
  comment?: string;
  created_at: string;
}
```

Keep all other interfaces unchanged.

## 2. API Client Updates

### File: /frontend/src/lib/api.ts

Add to `proofsAPI`:

```typescript
export const proofsAPI = {
  getUploadUrl: async (filename: string, contentType: string) =>
    (await api.get(`/proofs/storage/upload-url?filename=${encodeURIComponent(filename)}&content_type=${encodeURIComponent(contentType)}`)).data,
  
  create: async (proofData: any) => (await api.post('/proofs', proofData)).data,
  
  list: async () => (await api.get('/proofs')).data,
  
  get: async (proofId: string) => (await api.get(`/proofs/${proofId}`)).data,
  
  verify: async (proofId: string, approved: boolean, comment?: string) =>
    (await api.post(`/proofs/${proofId}/verifications`, { approved, comment })).data,
};
```

## 3. Updated VerificationQueue Component

### File: /frontend/src/components/proof/VerificationQueue.tsx

Download the fixed version from: /root/backend/VerificationQueue_fixed.tsx

## 4. Create Proof Detail Verification Page

### New File: /frontend/pages/verify/[proofId].tsx

Download the complete page from: /root/backend/verify_proof_page.tsx

## Testing Checklist

Once you apply these changes:

1. Update TypeScript types
2. Replace VerificationQueue with fixed version
3. Add API endpoints
4. Create new verification detail page
5. Navigate to /verification as a friend user
6. Click on a proof card
7. Verify the proof
8. Check milestone is marked complete

## Quick Start Commands

```bash
# Terminal 1: Start backend
cd /root/backend
source backend_env/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start frontend
cd /root/frontend
npm install
npm run dev
```

## Common Issues

- Proof Upload Fails: Check MinIO is running
- Images Not Loading: Verify MinIO public access
- Verifications Not Working: Check proof ID is correct
- Type Errors: Ensure types match between frontend/backend

All backend implementations are complete and tested! Frontend fixes are ready to deploy.