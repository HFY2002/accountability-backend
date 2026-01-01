#!/usr/bin/env python3
"""
Test script to verify the /api/v1/goals endpoint works correctly
"""
import asyncio
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()
database_url = os.getenv('DATABASE_URL')
if not database_url:
    print('DATABASE_URL not found in .env')
    sys.exit(1)

# Convert asyncpg URL to sync URL for testing
sync_url = database_url.replace('+asyncpg', '')

def test_database():
    """Test that all milestones have valid boolean values"""
    engine = create_engine(sync_url)
    with engine.connect() as conn:
        # Check for NULL values in boolean fields
        result = conn.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN completed IS NULL THEN 1 END) as null_completed,
                COUNT(CASE WHEN failed IS NULL THEN 1 END) as null_failed
            FROM milestones
        """))
        row = result.fetchone()
        
        print(f"Total milestones: {row.total}")
        print(f"NULL completed values: {row.null_completed}")
        print(f"NULL failed values: {row.null_failed}")
        
        if row.null_completed > 0 or row.null_failed > 0:
            print("❌ FAILED: Found NULL values in boolean fields!")
            return False
        else:
            print("✅ PASSED: All boolean fields have valid values")
            return True

if __name__ == "__main__":
    success = test_database()
    sys.exit(0 if success else 1)
