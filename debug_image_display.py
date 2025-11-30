#!/usr/bin/env python3
"""
Debug script to check why images aren't displaying.
Checks: proof URLs, MinIO accessibility, CORS, etc.
"""

import requests
import sys
import os

# Backend configuration
BACKEND_URL = "http://localhost:8000"
API_URL = f"{BACKEND_URL}/api/v1"
MINIO_URL = "http://localhost:9000"

def test_minio_accessibility():
    """Test if MinIO is accessible and responding"""
    print("=" * 60)
    print("🧪 Testing MinIO Accessibility")
    print("=" * 60)
    
    try:
        # Check MinIO health endpoint
        print(f"\n📍 Testing MinIO health endpoint: {MINIO_URL}/minio/health/live")
        response = requests.get(f"{MINIO_URL}/minio/health/live", timeout=5)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ MinIO is accessible")
        else:
            print(f"   ⚠️  Unexpected status: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Cannot reach MinIO: {e}")
        print("   💡 Check if MinIO is running on port 9000")
    
    print()

def test_bucket_policy():
    """Check MinIO bucket policy"""
    print("=" * 60)
    print("🧪 Checking MinIO bucket policy")
    print("=" * 60)
    
    # Try to list buckets anonymously (should fail if private)
    print(f"\n📍 Testing anonymous access to MinIO")
    try:
        response = requests.get(f"{MINIO_URL}/")
        print(f"   Anonymous list response: {response.status_code}")
        if response.status_code == 403:
            print("   ✅ Bucket is private (good)")
        elif response.status_code == 200:
            print("   ⚠️  Bucket is public (should be private)")
        else:
            print(f"   Status: {response.status_code}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()

def analyze_existing_proof():
    """Analyze an existing proof from the backend"""
    print("=" * 60)
    print("🧪 Testing with sample proof")
    print("=" * 60)
    
    # Use the proof ID from the logs
    proof_id = "662228b1-abd9-4505-95cc-46c57e409db5"
    print(f"\n📍 Using proof ID: {proof_id}")
    
    # Try to get the proof data (without auth for now)
    try:
        response = requests.get(f"{API_URL}/proofs/{proof_id}", timeout=5)
        print(f"   Get proof response: {response.status_code}")
        
        if response.status_code == 401:
            print("   ✅ Auth required (expected)")
            print("\n   💡 The proof endpoint works correctly")
        elif response.status_code == 200:
            proof = response.json()
            print(f"   ✅ Got proof data!")
            print(f"\n   Proof details:")
            print(f"   - ID: {proof.get('id')}")
            print(f"   - Status: {proof.get('status')}")
            print(f"   - Caption: {proof.get('caption', 'N/A')}")
            
            image_url = proof.get('image_url')
            if image_url:
                print(f"\n   🖼️  Image URL: {image_url}")
                
                # Check if it's a presigned URL
                if "X-Amz" in image_url:
                    print("   ✅ URL is presigned (contains AWS signature)")
                elif "/api/v1/proofs/storage/" in image_url:
                    print("   ❌ ERROR: Still using proxy URLs!")
                else:
                    print("   ⚠️  Unknown URL format")
                
                # Try to access the image URL
                print(f"\n   🔍 Testing image URL directly...")
                try:
                    response = requests.get(image_url, timeout=10)
                    print(f"   Image response: {response.status_code}")
                    
                    if response.status_code == 200:
                        content_type = response.headers.get('content-type', 'unknown')
                        size = len(response.content)
                        print(f"   ✅ Image accessible!")
                        print(f"   - Content-Type: {content_type}")
                        print(f"   - Size: {size} bytes")
                        
                        if 'image' not in content_type:
                            print(f"   ❌ WARNING: Not an image content type!")
                        
                    elif response.status_code == 403:
                        print("   ❌ Access denied (403)")
                        print("   💡 Possible CORS issue or signature problem")
                    elif response.status_code == 404:
                        print("   ❌ Image not found (404)")
                        print("   💡 Image might not exist in MinIO")
                    else:
                        print(f"   ⚠️  Unexpected status: {response.status_code}")
                        
                except requests.exceptions.Timeout:
                    print("   ❌ Request timed out")
                except Exception as e:
                    print(f"   ❌ Error accessing image: {e}")
                    
            else:
                print("   ❌ No image_url in proof data")
        else:
            print(f"   ⚠️  Unexpected response: {response.text}")
    except Exception as e:
        print(f"   ❌ Error getting proof: {e}")
    
    print()

def check_cors_configuration():
    """Check potential CORS issues"""
    print("=" * 60)
    print("🧪 Analyzing Potential CORS Issues")
    print("=" * 60)
    
    print("\n📍 Frontend-origin requests to MinIO:")
    print("   When the frontend loads <img src='minio-url'>")
    print("   the browser makes a GET request to MinIO")
    print()
    print("💡 Common CORS Issues:")
    print("   1. MinIO bucket doesn't allow Origin: localhost:*")
    print("   2. MinIO response missing Access-Control-Allow-Origin header")
    print("   3. Browser blocks response due to CORS policy")
    print()
    print("🔧 To fix CORS in MinIO:")
    print("   Use mc client:")
    print("   mc anonymous set download myminio/goal-proofs")
    print("   OR configure bucket policy")
    print()

def check_browser_console_errors():
    """What to look for in browser console"""
    print("=" * 60)
    print("🔍 What to Check in Browser Developer Console")
    print("=" * 60)
    
    print("\n📍 Open browser console (F12) and check:")
    print()
    print("1. Network tab:")
    print("   - Look for image requests")
    print("   - Check if image URL returns 200, 403, or fails")
    print("   - Look for CORS errors")
    print()
    print("2. Console tab:")
    print("   - CORS policy errors")
    print("   - Failed to load resource errors")
    print("   - Any JavaScript errors")
    print()

def main():
    print()
    print("🔧 Image Display Debug Tool")
    print("=" * 60)
    print()
    
    # Check MinIO
    test_minio_accessibility()
    
    # Check bucket policy
    test_bucket_policy()
    
    # Analyze existing proof
    analyze_existing_proof()
    
    # Check CORS
    check_cors_configuration()
    
    # Browser debugging tips
    check_browser_console_errors()
    
    print("=" * 60)
    print("🔧 Recommended Actions:")
    print("=" * 60)
    print()
    print("1. Check browser console for actual error messages")
    print("2. Test the image URL directly in a new browser tab")
    print("3. Use 'curl -v <image-url>' to see detailed headers")
    print("4. Verify MinIO CORS configuration")
    print("5. Check if the image actually exists in MinIO bucket")
    print()

if __name__ == "__main__":
    main()
