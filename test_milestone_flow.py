#!/usr/bin/env python3
"""
Quick test script for milestone proof verification
Tests backend endpoints with simulated data
"""

import asyncio
import httpx

async def test_backend():
    """Test backend endpoints"""
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        print("Testing backend endpoints...")
        
        # Test proofs endpoint
        response = await client.get("/api/v1/proofs")
        print(f"GET /proofs: {response.status_code}")
        
        response = await client.get("/docs")
        print(f"API docs: {response.status_code}")
        
        print("Backend is accessible!")

if __name__ == "__main__":
    asyncio.run(test_backend())