#!/usr/bin/env python3
"""
Fix MinIO CORS configuration to allow frontend to display images
"""

import boto3
import sys
import os

# Change to backend directory
os.chdir('/root/backend')
sys.path.insert(0, '/root/backend')

def set_minio_cors():
    """Configure CORS for MinIO bucket"""
    print("=" * 60)
    print("🔧 Configuring MinIO CORS")
    print("=" * 60)
    print()
    
    try:
        from app.core.config import settings
        
        # Create S3 client
        print("📍 Connecting to MinIO...")
        s3_client = boto3.client(
            's3',
            endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name='us-east-1'
        )
        
        # CORS configuration
        cors_configuration = {
            'CORSRules': [
                {
                    'AllowedHeaders': ['*'],
                    'AllowedMethods': ['GET', 'HEAD'],
                    'AllowedOrigins': [
                        'http://localhost:3000',
                        'http://127.0.0.1:3000',
                        'http://localhost:8000',
                        'http://127.0.0.1:8000'
                    ],
                    'ExposeHeaders': ['ETag'],
                    'MaxAgeSeconds': 3600
                }
            ]
        }
        
        # Apply CORS configuration
        print(f"📋 Setting CORS for bucket: {settings.PROOF_BUCKET}")
        s3_client.put_bucket_cors(
            Bucket=settings.PROOF_BUCKET,
            CORSConfiguration=cors_configuration
        )
        
        print(f"✅ CORS configuration applied successfully!")
        print()
        print("📋 CORS Rules:")
        for rule in cors_configuration['CORSRules']:
            print(f"   Allow Origin: {', '.join(rule['AllowedOrigins'])}")
            print(f"   Allow Methods: {', '.join(rule['AllowedMethods'])}")
            print(f"   Allow Headers: {', '.join(rule['AllowedHeaders'])}")
        print()
        
        # Test the CORS configuration
        print("🧪 Testing CORS configuration...")
        test_file = "cors-test.jpg"
        
        # Upload a test file
        with open('/root/Screenshot 2025-11-30 150833.jpg', 'rb') as f:
            s3_client.put_object(
                Bucket=settings.PROOF_BUCKET,
                Key=test_file,
                Body=f,
                ContentType='image/jpeg'
            )
        
        print(f"✅ Test file uploaded: {test_file}")
        
        # Generate presigned URL
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': settings.PROOF_BUCKET, 'Key': test_file},
            ExpiresIn=3600
        )
        
        print(f"🧪 Testing presigned URL with CORS...")
        print(f"URL: {presigned_url[:80]}...")
        
        # Test with Origin header (simulating browser)
        import requests
        
        response = requests.get(
            presigned_url,
            headers={'Origin': 'http://localhost:3000'},
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"✅ Image accessible!")
            
            # Check CORS headers
            cors_header = response.headers.get('Access-Control-Allow-Origin')
            if cors_header:
                print(f"✅ CORS header present: {cors_header}")
                print()
                print("🎉 SUCCESS! Images should now display in the frontend!")
                return True
            else:
                print(f"⚠️  CORS header missing: {cors_header}")
                print("   This might still cause issues")
                return False
        else:
            print(f"❌ Failed to access image: {response.status_code}")
            return False
        
    except Exception as e:
        print(f"❌ Error configuring CORS: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = set_minio_cors()
    sys.exit(0 if success else 1)
