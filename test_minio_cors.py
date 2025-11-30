#!/usr/bin/env python3
"""
Test MinIO CORS configuration and image accessibility
"""

import requests
import os
import sys

MINIO_URL = "http://localhost:9000"
BUCKET_NAME = "goal-proofs"
IMAGE_PATH = "/root/Screenshot 2025-11-30 150833.jpg"

def test_direct_minio_upload():
    """Test uploading and accessing an image directly from MinIO"""
    print("=" * 60)
    print("🧪 Direct MinIO Upload and Access Test")
    print("=" * 60)
    
    # First, let's use boto3 to interact with MinIO properly
    try:
        import boto3
        from app.core.config import settings
        
        print("\n📍 Setting up MinIO client...")
        s3_client = boto3.client(
            's3',
            endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name='us-east-1'
        )
        
        # Upload test image
        print(f"\n📤 Uploading test image...")
        object_name = "test-image-debug.jpg"
        
        with open(IMAGE_PATH, 'rb') as f:
            s3_client.put_object(
                Bucket=settings.PROOF_BUCKET,
                Key=object_name,
                Body=f,
                ContentType='image/jpeg'
            )
        
        print(f"✅ Image uploaded to: {settings.PROOF_BUCKET}/{object_name}")
        
        # Generate presigned URL
        print(f"\n🔗 Generating presigned URL...")
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': settings.PROOF_BUCKET, 'Key': object_name},
            ExpiresIn=3600  # 1 hour
        )
        
        print(f"✅ Presigned URL generated:")
        print(f"   {presigned_url[:100]}...")
        
        # Test accessing the URL
        print(f"\n🧪 Testing URL access...")
        response = requests.get(presigned_url, timeout=10)
        
        print(f"   Response status: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('content-type', 'unknown')}")
        print(f"   Content-Length: {len(response.content)} bytes")
        
        if response.status_code == 200:
            print(f"✅ Image is accessible!")
            
            # Test CORS headers
            print(f"\n🧪 Checking CORS headers...")
            cors_headers = {k: v for k, v in response.headers.items() if 'access-control' in k.lower()}
            if cors_headers:
                for k, v in cors_headers.items():
                    print(f"   {k}: {v}")
            else:
                print(f"   ⚠️  No CORS headers found in response")
                print(f"   💡 This may cause CORS issues in browser")
            
            # Test with Origin header (simulating browser)
            print(f"\n🧪 Testing with Origin header (browser simulation)...")
            response_with_origin = requests.get(
                presigned_url,
                headers={'Origin': 'http://localhost:3000'},
                timeout=10
            )
            
            print(f"   Response status: {response_with_origin.status_code}")
            
            cors_headers = {k: v for k, v in response_with_origin.headers.items() if 'access-control' in k.lower()}
            if cors_headers:
                print(f"   ✅ CORS headers present:")
                for k, v in cors_headers.items():
                    print(f"      {k}: {v}")
            else:
                print(f"   ❌ No CORS headers - browser will block this!")
                
            return presigned_url
        else:
            print(f"❌ Failed to access image")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def check_minio_cors_policy():
    """Check if MinIO has CORS configured"""
    print("\n" + "=" * 60)
    print("🧪 Checking MinIO CORS Configuration")
    print("=" * 60)
    
    try:
        import boto3
        from app.core.config import settings
        
        s3_client = boto3.client(
            's3',
            endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name='us-east-1'
        )
        
        # Try to get bucket CORS configuration
        try:
            cors_config = s3_client.get_bucket_cors(Bucket=settings.PROOF_BUCKET)
            print(f"\n✅ CORS configuration found:")
            print(f"   {cors_config}")
        except Exception as e:
            if 'NoSuchCORSConfiguration' in str(e):
                print(f"\n❌ No CORS configuration found for bucket: {settings.PROOF_BUCKET}")
                print(f"   This will cause CORS errors in browsers!")
                print(f"\n🔧 To fix, run:")
                print(f"   mc alias set myminio http://localhost:9000 minioadmin minioadmin")
                print(f"   mc anonymous set download myminio/{settings.PROOF_BUCKET}")
            else:
                print(f"   Error: {e}")
                
    except Exception as e:
        print(f"❌ Error checking CORS: {e}")

def test_browser_cors_simulation():
    """Simulate what a browser does"""
    print("\n" + "=" * 60)
    print("🧪 Browser CORS Simulation")
    print("=" * 60)
    
    try:
        import boto3
        from app.core.config import settings
        
        s3_client = boto3.client(
            's3',
            endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name='us-east-1'
        )
        
        # Generate a presigned URL
        object_name = "test-image-debug.jpg"
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': settings.PROOF_BUCKET, 'Key': object_name},
            ExpiresIn=3600
        )
        
        print(f"\n📍 Testing presigned URL with various conditions...")
        
        # Simulate browser preflight (OPTIONS request)
        print(f"\n1. Testing OPTIONS preflight request...")
        try:
            response = requests.options(
                presigned_url,
                headers={
                    'Origin': 'http://localhost:3000',
                    'Access-Control-Request-Method': 'GET'
                },
                timeout=5
            )
            print(f"   OPTIONS status: {response.status_code}")
            print(f"   OPTIONS headers: {dict(response.headers)}")
        except Exception as e:
            print(f"   OPTIONS failed: {e}")
        
        # Simulate simple GET with Origin header
        print(f"\n2. Testing GET with Origin header...")
        response = requests.get(
            presigned_url,
            headers={'Origin': 'http://localhost:3000'},
            timeout=10
        )
        print(f"   GET status: {response.status_code}")
        
        cors_headers = {}
        for header_name, header_value in response.headers.items():
            if header_name.lower().startswith('access-control'):
                cors_headers[header_name] = header_value
        
        if cors_headers:
            print(f"   ✅ CORS headers present:")
            for k, v in cors_headers.items():
                print(f"      {k}: {v}")
        else:
            print(f"   ❌ NO CORS HEADERS - Browser will block this!")
            print(f"\n   🐛 This is likely why images don't display!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("=" * 70)
    print("🔧 MinIO CORS and Image Access Comprehensive Test")
    print("=" * 70)
    
    # Change to backend directory
    os.chdir('/root/backend')
    sys.path.insert(0, '/root/backend')
    
    # Test 1: Direct upload and access
    presigned_url = test_direct_minio_upload()
    
    # Test 2: Check CORS configuration
    check_minio_cors_policy()
    
    # Test 3: Browser simulation
    test_browser_cors_simulation()
    
    print("\n" + "=" * 70)
    print("📋 SUMMARY")
    print("=" * 70)
    print()
    
    if presigned_url:
        print("✅ Image upload and presigned URL generation works")
        print(f"✅ Direct access to presigned URLs works")
        print()
        print("🔍 The issue is likely CORS configuration in MinIO")
        print()
        print("🔧 TO FIX:")
        print("   1. Install mc (MinIO client)")
        print("   2. Configure MinIO:")
        print(f"      mc alias set myminio http://localhost:9000 minioadmin minioadmin")
        print(f"      mc anonymous set download myminio/{BUCKET_NAME}")
        print()
        print("   Or set bucket policy:")
        print(f"      mc policy set public myminio/{BUCKET_NAME}")
        print()
    else:
        print("❌ Image upload/access test failed")
    
    print()
    print("💡 After fixing CORS, restart MinIO and try again")
    print()

if __name__ == "__main__":
    main()
