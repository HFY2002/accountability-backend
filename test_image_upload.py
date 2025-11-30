#!/usr/bin/env python3
"""
Test script to verify image upload and display functionality.
Tests the complete flow: login -> get upload URL -> upload image -> create proof -> view proof
"""

import requests
import sys
import json
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8000"
API_URL = f"{BASE_URL}/api/v1"
IMAGE_PATH = "/root/Screenshot 2025-11-30 150833.jpg"
TEST_USERNAME = "testuser"
TEST_PASSWORD = "testpass123"

def login(username, password):
    """Login and return JWT token"""
    print(f"🔑 Logging in as {username}...")
    response = requests.post(
        f"{API_URL}/auth/login",
        data={"username": username, "password": password}
    )
    
    if response.status_code != 200:
        print(f"❌ Login failed: {response.status_code}")
        print(response.text)
        return None
    
    token = response.json().get("access_token")
    print(f"✅ Login successful! Token: {token[:20]}...")
    return token

def get_upload_url(token, filename, content_type):
    """Get presigned upload URL from backend"""
    print(f"📤 Getting upload URL for {filename}...")
    
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "filename": filename,
        "content_type": content_type
    }
    
    response = requests.get(
        f"{API_URL}/proofs/storage/upload-url",
        headers=headers,
        params=params
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to get upload URL: {response.status_code}")
        print(response.text)
        return None
    
    data = response.json()
    print(f"✅ Got upload URL! Public URL: {data['public_url']}")
    print(f"   File path: {data['file_path']}")
    return data

def upload_image_to_minio(upload_url, image_path, content_type):
    """Upload image directly to MinIO using presigned URL"""
    print(f"📸 Uploading image to MinIO...")
    
    with open(image_path, 'rb') as f:
        files = {'file': (image_path, f, content_type)}
        response = requests.put(
            upload_url,
            data=f.read(),
            headers={"Content-Type": content_type}
        )
    
    if response.status_code != 200:
        print(f"❌ Upload failed: {response.status_code}")
        print(f"Response: {response.text}")
        return False
    
    print(f"✅ Upload successful!")
    return True

def create_proof(token, goal_id, file_path, caption="Test proof image"):
    """Create a proof with the uploaded image"""
    print(f"📝 Creating proof for goal {goal_id}...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    data = {
        "goal_id": goal_id,
        "storage_key": file_path,
        "caption": caption
    }
    
    response = requests.post(
        f"{API_URL}/proofs",
        headers=headers,
        json=data
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to create proof: {response.status_code}")
        print(response.text)
        return None
    
    proof = response.json()
    print(f"✅ Proof created successfully!")
    print(f"   Proof ID: {proof['id']}")
    print(f"   Image URL: {proof['image_url']}")
    return proof

def get_proof_details(token, proof_id):
    """Get proof details including image URL"""
    print(f"🔍 Getting proof details for {proof_id}...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{API_URL}/proofs/{proof_id}",
        headers=headers
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to get proof: {response.status_code}")
        print(response.text)
        return None
    
    proof = response.json()
    print(f"✅ Got proof details!")
    print(f"   Status: {proof['status']}")
    print(f"   Image URL: {proof['image_url']}")
    return proof

def test_image_url(image_url):
    """Test if the image URL is accessible"""
    print(f"🖼️  Testing image URL accessibility...")
    
    response = requests.get(image_url)
    
    if response.status_code != 200:
        print(f"❌ Failed to access image: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        return False
    
    content_type = response.headers.get('content-type', 'unknown')
    content_length = len(response.content)
    
    print(f"✅ Image accessible!")
    print(f"   Content-Type: {content_type}")
    print(f"   Size: {content_length} bytes")
    return True

def list_user_goals(token):
    """List user's goals to find one to test with"""
    print(f"📋 Getting user's goals...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{API_URL}/goals",
        headers=headers
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to get goals: {response.status_code}")
        return None
    
    goals = response.json()
    if not goals:
        print("❌ No goals found for user")
        return None
    
    print(f"✅ Found {len(goals)} goals")
    for i, goal in enumerate(goals[:3]):  # Show first 3
        print(f"   {i+1}. {goal['title']} (ID: {goal['id']})")
    
    return goals[0]['id']  # Return first goal

def main():
    print("=" * 60)
    print("🧪 TESTING IMAGE UPLOAD AND DISPLAY FUNCTIONALITY")
    print("=" * 60)
    print()
    
    # Step 1: Login
    token = login(TEST_USERNAME, TEST_PASSWORD)
    if not token:
        sys.exit(1)
    print()
    
    # Step 2: Get a goal to test with
    goal_id = list_user_goals(token)
    if not goal_id:
        print("\n⚠️  Creating test goal...")
        # For now, we'll use a dummy goal_id - replace with actual creation logic if needed
        goal_id = "00000000-0000-0000-0000-000000000000"
    print()
    
    # Step 3: Get upload URL
    filename = Path(IMAGE_PATH).name
    content_type = "image/jpeg"
    upload_data = get_upload_url(token, filename, content_type)
    if not upload_data:
        sys.exit(1)
    print()
    
    # Step 4: Upload image
    success = upload_image_to_minio(upload_data['upload_url'], IMAGE_PATH, content_type)
    if not success:
        sys.exit(1)
    print()
    
    # Step 5: Create proof
    proof = create_proof(token, goal_id, upload_data['file_path'])
    if not proof:
        sys.exit(1)
    print()
    
    # Step 6: Verify proof details
    proof_details = get_proof_details(token, proof['id'])
    if not proof_details:
        sys.exit(1)
    print()
    
    # Step 7: Test image URL directly
    success = test_image_url(proof_details['image_url'])
    if not success:
        sys.exit(1)
    print()
    
    print("=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print()
    print("📝 Summary:")
    print(f"   - Image uploaded successfully")
    print(f"   - Proof created with ID: {proof['id']}")
    print(f"   - Image URL is accessible: {proof_details['image_url']}")
    print("   - Frontend should display the image correctly")
    print()
    print("💡 Try viewing this proof in the frontend to see the image!")

if __name__ == "__main__":
    main()
