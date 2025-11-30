# Image Display Issue - CORS Configuration

## The Problem

Images uploaded to MinIO are not displaying in the frontend even though:
- Images upload successfully
- Presigned URLs are generated correctly
- The proxy solution was replaced with presigned URLs
- Backend shows no errors

## Root Cause

**CORS (Cross-Origin Resource Sharing) configuration in MinIO**

When the frontend (running at `http://localhost:3000`) tries to load an image from MinIO (at `http://localhost:9000`), the browser sends an `Origin` header. MinIO must respond with appropriate CORS headers (`Access-Control-Allow-Origin`) to allow the browser to display the image.

Without proper CORS headers, the browser will block the image load, showing a broken image icon.

## Solution

### Option 1: Configure MinIO Bucket Policy (Quick Fix)

1. **Install MinIO Client (mc)**:
   ```bash
   wget https://dl.min.io/client/mc/release/linux-amd64/mc
   chmod +x mc
   sudo mv mc /usr/local/bin/
   ```

2. **Configure MinIO access**:
   ```bash
   mc alias set myminio http://localhost:9000 minioadmin minioadmin
   ```

3. **Set bucket policy to allow public downloads**:
   ```bash
   mc anonymous set download myminio/goal-proofs
   ```

4. **Restart MinIO**:
   ```bash
   # If using Docker
   docker restart minio
   
   # If running directly
   pkill minio
   minio server /data
   ```

### Option 2: Configure CORS Rules (More Secure)

Use boto3 to set CORS rules:

```python
import boto3

s3_client = boto3.client(
    's3',
    endpoint_url='http://localhost:9000',
    aws_access_key_id='minioadmin',
    aws_secret_access_key='minioadmin',
    region_name='us-east-1'
)

# Set CORS rules
cors_configuration = {
    'CORSRules': [{
        'AllowedOrigins': ['http://localhost:3000'],
        'AllowedMethods': ['GET', 'HEAD'],
        'AllowedHeaders': ['*'],
        'ExposeHeaders': ['ETag'],
        'MaxAgeSeconds': 3600
    }]
}

s3_client.put_bucket_cors(
    Bucket='goal-proofs',
    CORSConfiguration=cors_configuration
)
```

### Option 3: Enable Browser CORS (Development only)

For local development, you can use a browser extension to disable CORS:
- Chrome: "CORS Unblock" extension
- Firefox: "CORS Everywhere" extension

**Warning**: Only use this for development, never in production!

## Verification

After configuring CORS, verify it works:

1. **Upload a new proof image** (old ones may still have issues)
2. **Copy the image URL** from the verification queue or proof details
3. **Test in browser**:
   - Open browser console (F12)
   - Go to Network tab
   - Load the page - watch for image requests
   - Image should load with status 200

4. **Test with curl**:
   ```bash
   curl -H "Origin: http://localhost:3000" \
        -H "Access-Control-Request-Method: GET" \
        -X GET \
        "<presigned-url>" \
        -v
   ```
   
   Look for `Access-Control-Allow-Origin: http://localhost:3000` in response headers

## Technical Details

**Current Flow**:
1. Frontend uploads image → gets presigned PUT URL → uploads to MinIO
2. Backend stores presigned GET URL in database
3. Frontend loads image via `<img src="presigned-url">`
4. Browser sends GET request with `Origin: http://localhost:3000`
5. MinIO responds with image BUT missing CORS headers
6. **Browser blocks image** → Shows broken image icon

**Expected Flow**:
1. Frontend uploads image → gets presigned PUT URL → uploads to MinIO 
2. Backend stores presigned GET URL in database
3. Frontend loads image via `<img src="presigned-url">`
4. Browser sends GET request with `Origin: http://localhost:3000`
5. MinIO responds with image AND `Access-Control-Allow-Origin: http://localhost:3000`
6. **Browser displays image** → Image visible ✅

## Alternative Solutions

If CORS configuration is not an option:

1. **Use a backend proxy** (previous solution - had auth issues)
2. **Download images to backend** and serve from same origin
3. **Use a CDN** that handles CORS properly
4. **Host frontend and MinIO on same domain** (e.g., via nginx reverse proxy)

## Testing Presigned URLs

To verify a presigned URL works:

```bash
# Get the presigned URL from the proof response
curl -H "Origin: http://localhost:3000" \
     "http://localhost:9000/goal-proofs/filename.jpg?<params>" \
     -v | head
```

Check for:
- `HTTP/1.1 200 OK` response
- `Content-Type: image/jpeg` header
- `Access-Control-Allow-Origin: http://localhost:3000` header

## Summary

The image display issue is caused by **missing CORS headers** from MinIO. Configure MinIO to allow requests from your frontend origin (`http://localhost:3000`) and images will display correctly.
