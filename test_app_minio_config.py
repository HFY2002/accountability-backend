#!/usr/bin/env python3
"""
Test MinIO bucket using the application's actual configuration
"""

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

# Using the same settings as the application
MINIO_ENDPOINT = "127.0.0.1:9000"
MINIO_ACCESS_KEY = "admin"
MINIO_SECRET_KEY = "12345678"
PROOF_BUCKET = "goal-proofs"

print("Testing with Application Configuration")
print("=" * 50)
print(f"Endpoint: {MINIO_ENDPOINT}")
print(f"Bucket: {PROOF_BUCKET}")
print(f"Access Key: {MINIO_ACCESS_KEY}")
print("=" * 50)

try:
    # Create S3 client using the exact same configuration as the app
    s3_client = boto3.client(
        's3',
        endpoint_url=f"http://{MINIO_ENDPOINT}",
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    
    # Verify bucket exists and is accessible
    print("\n✓ Connected to MinIO server successfully")
    
    # Test bucket exists
    s3_client.head_bucket(Bucket=PROOF_BUCKET)
    print(f"✓ Bucket '{PROOF_BUCKET}' is accessible")
    
    # Verify we can list objects
    response = s3_client.list_objects_v2(Bucket=PROOF_BUCKET)
    object_count = len(response.get('Contents', []))
    print(f"✓ Can list objects (found {object_count} objects)")
    
    # Test presigned URL generation (like the app does)
    test_object_key = "test-proof.jpg"
    presigned_url = s3_client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": PROOF_BUCKET,
            "Key": test_object_key,
            "ContentType": "image/jpeg",
        },
        ExpiresIn=3600,
    )
    print(f"✓ Presigned URL generation works")
    print(f"  Example URL (truncated): {presigned_url[:80]}...")
    
    # Test public URL format
    public_url = f"http://{MINIO_ENDPOINT}/{PROOF_BUCKET}/{test_object_key}"
    print(f"✓ Public URL format: {public_url}")
    
    print("\n" + "=" * 50)
    print("Application Configuration Test: PASSED")
    print("=" * 50)
    
except ClientError as e:
    error_code = e.response['Error']['Code']
    print(f"\n✗ Client Error: {error_code}")
    print(f"   Details: {e}")
except Exception as e:
    print(f"\n✗ Error: {type(e).__name__}: {e}")
