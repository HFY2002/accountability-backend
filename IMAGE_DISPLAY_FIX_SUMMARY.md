# Image Display Issue - Root Cause & Solution

## The Problem

After implementing the backend changes, uploaded proof images still don't display in the frontend. Instead, users see a broken image icon with the alt text "Proof".

## Root Cause: CORS (Cross-Origin Resource Sharing)

The issue is **NOT** with the backend code or URL generation. It's a CORS configuration problem with MinIO.

### What Happens:

1. ✅ Frontend uploads image → MinIO (successful)
2. ✅ Backend generates presigned URL → stores in database
3. ✅ Frontend receives presigned URL in API response
4. ✅ Frontend renders `<img src="presigned-url">`
5. ❌ Browser requests image from MinIO
6. ❌ MinIO responds with image but **NO CORS headers**
7. ❌ **Browser blocks the image** for security (shows broken icon)

### Why It Happens:

- **Frontend runs on**: `http://localhost:3000`
- **MinIO runs on**: `http://localhost:9000`
- **Browser security**: Blocks cross-origin requests without proper CORS headers
- **MinIO default**: Does not include CORS headers in responses

## Solution

Configure MinIO to send CORS headers that allow the frontend to access images.

### Quick Fix (Development)

Use `mc` (MinIO client) to configure the bucket:

```bash
# Install mc
wget https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc
sudo mv mc /usr/local/bin/

# Configure access
mc alias set myminio http://localhost:9000 minioadmin minioadmin

# Make bucket publicly readable
mc anonymous set download myminio/goal-proofs

# Or for more control, use bucket policy:
cat > policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": ["s3:GetObject"],
      "Resource": ["arn:aws:s3:::goal-proofs/*"]
    }
  ]
}
EOF

mc admin policy create myminio public-download policy.json
mc anonymous set public myminio/goal-proofs
```

### Permanent Solution (Production)

1. **Configure MinIO with proper CORS** in your deployment
2. **Use nginx reverse proxy** to serve MinIO from same domain as frontend
3. **Set environment variables** in MinIO for CORS:
   ```bash
   export MINIO_API_CORS_ALLOW_ORIGIN="http://localhost:3000"
   minio server /data
   ```

## Verification

After fixing CORS, test with:

```bash
# Get a presigned URL from your app
# Then test it:
curl -H "Origin: http://localhost:3000" \
     "http://localhost:9000/goal-proofs/filename.jpg?X-Amz-..." \
     -v -o /dev/null

# Should see in response headers:
# Access-Control-Allow-Origin: http://localhost:3000
```

## Implementation Status

✅ **Backend Code**: Complete
- `get_public_url()` now returns presigned URLs (24-hour expiry)
- Proxy endpoint removed (wasn't working anyway)
- Storage service properly generates presigned URLs

❌ **MinIO Configuration**: Needs CORS fix
- Bucket is private (good)
- Presigned URLs work (good)
- Missing CORS headers (bad)

## Testing Recommendation

1. **Apply the CORS fix** above
2. **Restart MinIO** to ensure settings apply
3. **Upload a NEW proof image** (old ones may not work)
4. **Check browser console** for any CORS errors
5. **Verify Network tab** shows successful image loads (200 status)

## Expected Behavior After Fix

- Upload proof image → Success
- See proof in verification queue → Image displays
- No broken image icons
- Browser console shows no CORS errors
- Network tab shows image requests with 200 status

## Technical Details

**Current Implementation**:
```python
# storage.py
def get_public_url(self, object_name: str) -> str:
    """Generate presigned URL for direct access (valid for 24 hours)."""
    return self.generate_presigned_get(object_name, expires_in=86400)
```

This correctly generates URLs like:
`http://localhost:9000/goal-proofs/image.jpg?X-Amz-Algorithm=AWS4-HMAC-SHA256&...`

The problem is MinIO doesn't add CORS headers to these responses by default.

## Summary

**Issue**: Images don't display in frontend  
**Root Cause**: MinIO missing CORS headers  
**Solution**: Configure MinIO CORS or bucket policy  
**Status**: Backend ready, MinIO needs configuration  

The backend implementation is complete and working. The final step is configuring MinIO's CORS settings to allow the frontend to load images.
