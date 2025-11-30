#!/usr/bin/env python3
"""
Test URL generation logic without requiring a running server.
"""

import sys
import re

def test_storage_service():
    """Test the storage service generate_presigned_get and get_public_url"""
    print("=" * 60)
    print("🧪 Testing Storage Service URL Generation")
    print("=" * 60)
    print()
    
    # Import the storage service
    try:
        from app.services.storage import storage_service
        from app.core.config import settings
        print(f"✅ Storage service imported successfully")
        print(f"   MinIO endpoint: {settings.MINIO_ENDPOINT}")
        print(f"   Proof bucket: {settings.PROOF_BUCKET}")
        print()
    except Exception as e:
        print(f"❌ Failed to import: {e}")
        return False
    
    # Test presigned URL generation
    test_key = "123e4567-e89b-12d3-a456-426614174000.jpg"
    print(f"🧪 Testing presigned URL generation for: {test_key}")
    
    presigned_url = storage_service.generate_presigned_get(test_key, expires_in=3600)
    if not presigned_url:
        print("❌ Failed to generate presigned URL")
        return False
    
    print(f"✅ Presigned URL generated:")
    print(f"   {presigned_url[:80]}...")
    print()
    
    # Verify URL format
    if settings.MINIO_ENDPOINT not in presigned_url:
        print("❌ URL doesn't contain MinIO endpoint")
        return False
    
    if test_key not in presigned_url:
        print("❌ URL doesn't contain object key")
        return False
    
    if "X-Amz" not in presigned_url:
        print("❌ URL doesn't contain AWS signature parameters")
        return False
    
    print("✅ Presigned URL format is correct")
    print()
    
    # Test get_public_url (should now return presigned URL)
    print(f"🧪 Testing get_public_url for: {test_key}")
    public_url = storage_service.get_public_url(test_key)
    
    if not public_url:
        print("❌ Failed to generate public URL")
        return False
    
    print(f"✅ Public URL generated:")
    print(f"   {public_url[:80]}...")
    print()
    
    # Verify it's a presigned URL (not a proxy URL)
    if "/api/v1/proofs/storage/" in public_url:
        print("❌ ERROR: Still using proxy URLs instead of presigned URLs!")
        return False
    
    if "X-Amz" not in public_url:
        print("❌ ERROR: Public URL is not a presigned URL!")
        return False
    
    print("✅ Public URL is correctly a presigned URL")
    print()
    
    # Test object key extraction
    print(f"🧪 Testing object key extraction from URL...")
    extracted_key = storage_service.get_object_key_from_url(public_url)
    
    if extracted_key != test_key:
        print(f"❌ Incorrect key extracted. Expected: {test_key}, Got: {extracted_key}")
        return False
    
    print(f"✅ Object key extracted correctly: {extracted_key}")
    print()
    
    return True

def test_url_accessibility():
    """Test if MinIO is accessible"""
    print("=" * 60)
    print("🧪 Testing MinIO Accessibility")
    print("=" * 60)
    print()
    
    try:
        import requests
        from app.core.config import settings
        
        # Try to access MinIO health check
        minio_url = f"http://{settings.MINIO_ENDPOINT}/minio/health/live"
        print(f"   Testing MinIO health: {minio_url}")
        
        response = requests.get(minio_url, timeout=5)
        print(f"   Response: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ MinIO is accessible")
        else:
            print(f"⚠️  MinIO returned status {response.status_code}")
            
    except Exception as e:
        print(f"⚠️  Could not reach MinIO: {e}")
        print("   This might be normal if MinIO is not running")
    
    print()
    return True

def main():
    print()
    print("🔍 Backend Image Display Solution Test")
    print("=" * 60)
    print()
    
    # Test storage service
    if not test_storage_service():
        sys.exit(1)
    
    # Test MinIO connectivity
    test_url_accessibility()
    
    print("=" * 60)
    print("✅ STORAGE SERVICE TESTS PASSED!")
    print("=" * 60)
    print()
    print("📋 Summary:")
    print("   ✓ Presigned URLs are generated correctly")
    print("   ✓ URLs use MinIO directly (not proxy)")
    print("   ✓ URLs contain proper AWS signature parameters")
    print("   ✓ Object key extraction works correctly")
    print()
    print("🚀 The solution is ready!")
    print()
    print("💡 Manual testing instructions:")
    print("   1. Start the backend: uvicorn app.main:app --reload")
    print("   2. Start the frontend (in another terminal)")
    print("   3. Login to the frontend")
    print("   4. Create a goal or open an existing one")
    print("   5. Add a milestone")
    print("   6. Upload the test image: /root/Screenshot 2025-11-30 150833.jpg")
    print("   7. Submit proof for the milestone")
    print("   8. Check verification queue - the image should display correctly!")
    print()

if __name__ == "__main__":
    import os
    os.chdir('/root/backend')
    sys.path.insert(0, '/root/backend')
    
    main()
