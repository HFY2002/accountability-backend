#!/usr/bin/env python3
"""
Test MinIO CORS and image display with your existing MinIO setup
"""

import os
import sys
import requests

os.chdir('/root/backend')
sys.path.insert(0, '/root/backend/backend_env/lib/python3.12/site-packages')
sys.path.insert(0, '/root/backend')

# Load MinIO config
minio_config = {}
with open('/root/infra-setup/minio.env', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            key, value = line.split('=', 1)
            minio_config[key] = value

# Handle variable expansion for MINIO_API_PORT
MINIO_API_PORT = minio_config.get('MINIO_API_PORT', '9000')
MINIO_SERVER_URL = minio_config.get('MINIO_SERVER_URL', 'http://127.0.0.1:9000')

# Replace ${MINIO_API_PORT} if present
if '${MINIO_API_PORT}' in MINIO_SERVER_URL:
    MINIO_SERVER_URL = MINIO_SERVER_URL.replace('${MINIO_API_PORT}', MINIO_API_PORT)

MINIO_ACCESS_KEY = minio_config.get('MINIO_ROOT_USER', 'admin')
MINIO_SECRET_KEY = minio_config.get('MINIO_ROOT_PASSWORD', '12345678')
BUCKET_NAME = 'goal-proofs'

print(f"🔍 Using MinIO: {MINIO_SERVER_URL}")

def test_minio_upload_and_access():
    """Test uploading and accessing image from MinIO"""
    import boto3
    
    print("=" * 70)
    print("🔍 Testing MinIO Upload and Access")
    print("=" * 70)
    print(f"\n📍 MinIO: {MINIO_SERVER_URL}")
    print(f"📍 Bucket: {BUCKET_NAME}")
    
    # Connect to MinIO
    s3_client = boto3.client(
        's3',
        endpoint_url=MINIO_SERVER_URL,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        region_name='us-east-1'
    )
    
    # Upload image
    test_file = "/root/Screenshot 2025-11-30 150833.jpg"
    object_key = "debug-test-image.jpg"
    
    print(f"\n📤 Uploading: {test_file}")
    with open(test_file, 'rb') as f:
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=object_key,
            Body=f,
            ContentType='image/jpeg'
        )
    print("✅ Upload successful")
    
    # Generate presigned URL
    print(f"\n🔗 Generating presigned URL for: {object_key}")
    presigned_url = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': BUCKET_NAME, 'Key': object_key},
        ExpiresIn=3600
    )
    print(f"URL: {presigned_url[:120]}...")
    
    # Test direct access
    print(f"\n🧪 Testing direct access...")
    response = requests.get(presigned_url, timeout=10)
    print(f"Status: {response.status_code}, Size: {len(response.content)} bytes")
    
    # Test with Origin header (browser simulation)
    print(f"\n🧪 Testing with Origin header (like browser does)...")
    response = requests.get(
        presigned_url,
        headers={'Origin': 'http://localhost:3000'},
        timeout=10
    )
    print(f"Status: {response.status_code}")
    
    cors_header = response.headers.get('Access-Control-Allow-Origin')
    if cors_header:
        print(f"✅ CORS header present: {cors_header}")
        return True
    else:
        print("❌ NO CORS HEADERS - this is why images don't display!")
        return False

def test_storage_service():
    """Test the storage service URL generation"""
    print("\n" + "=" * 70)
    print("🧪 Testing Storage Service")
    print("=" * 70)
    
    from app.services.storage import storage_service
    
    test_key = "test-image-123.jpg"
    url = storage_service.get_public_url(test_key)
    
    print(f"\n🔗 Generated URL for: {test_key}")
    print(f"URL: {url}")
    print()
    
    if "X-Amz" in url and MINIO_SERVER_URL in url:
        print("✅ Storage service generates presigned URLs correctly")
        return True
    else:
        print("❌ Storage service not generating presigned URLs")
        return False

def main():
    print()
    print("🔧 Image Display Test")
    print("=" * 70)
    print()
    
    # Test storage service
    storage_ok = test_storage_service()
    
    # Test MinIO directly
    minio_ok = test_minio_upload_and_access()
    
    print("\n" + "=" * 70)
    print("📋 TEST RESULTS")
    print("=" * 70)
    print()
    
    if storage_ok:
        print("✅ Backend generates presigned URLs correctly")
    else:
        print("❌ Backend URL generation has issues")
    
    if minio_ok:
        print("✅ MinIO has CORS configured - images should display!")
    else:
        print("❌ MinIO missing CORS - images won't display in browser")
        print()
        print("🔧 FIX NEEDED:")
        print("   Run: mc anonymous set download myminio/goal-proofs")
        print("   Then upload NEW images to test")
    
    print()

if __name__ == "__main__":
    main()
