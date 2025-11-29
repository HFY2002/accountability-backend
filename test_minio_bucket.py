#!/usr/bin/env python3
"""
Test MinIO bucket 'goal-proofs' accessibility and configuration
"""

import boto3
import json
from botocore.client import Config
from botocore.exceptions import ClientError, EndpointConnectionError

def test_minio_bucket():
    # MinIO connection settings
    endpoint_url = "http://127.0.0.1:9000"
    access_key = "admin"
    secret_key = "12345678"
    bucket_name = "goal-proofs"
    
    print("=" * 60)
    print("Testing MinIO Bucket Configuration")
    print("=" * 60)
    print(f"Endpoint: {endpoint_url}")
    print(f"Bucket: {bucket_name}")
    print(f"Access Key: {access_key}")
    print("=" * 60)
    
    try:
        # Create S3 client for MinIO
        s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version='s3v4'),
            region_name='us-east-1'  # MinIO ignores region but boto3 requires it
        )
        
        # Test 1: Check if bucket exists
        print("\n1. Checking if bucket exists...")
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            print(f"   ✓ Bucket '{bucket_name}' exists")
        except ClientError as e:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                print(f"   ✗ Bucket '{bucket_name}' does not exist")
            elif error_code == 403:
                print(f"   ✗ Access denied to bucket '{bucket_name}'")
            else:
                print(f"   ✗ Error checking bucket: {e}")
            return
        
        # Test 2: Get bucket policy information
        print("\n2. Retrieving bucket policy...")
        try:
            policy = s3_client.get_bucket_policy(Bucket=bucket_name)
            policy_dict = json.loads(policy['Policy'])
            print(f"   ✓ Bucket policy found:")
            print(f"   Policy: {json.dumps(policy_dict, indent=6)}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucketPolicy':
                print(f"   ⚠ No bucket policy configured (bucket is private by default)")
            else:
                print(f"   ✗ Error retrieving bucket policy: {e}")
        
        # Test 3: Get bucket ACL
        print("\n3. Retrieving bucket ACL...")
        try:
            acl = s3_client.get_bucket_acl(Bucket=bucket_name)
            print(f"   ✓ Bucket ACL found:")
            for grant in acl.get('Grants', []):
                grantee = grant.get('Grantee', {})
                permission = grant.get('Permission', '')
                grantee_type = grantee.get('Type', '')
                grantee_uri = grantee.get('URI', '')
                print(f"   - {grantee_type}: {permission}")
                if grantee_uri:
                    print(f"     URI: {grantee_uri}")
        except ClientError as e:
            print(f"   ✗ Error retrieving bucket ACL: {e}")
        
        # Test 4: List objects in bucket
        print("\n4. Listing objects in bucket...")
        try:
            response = s3_client.list_objects_v2(Bucket=bucket_name)
            if 'Contents' in response:
                objects = response['Contents']
                print(f"   ✓ Found {len(objects)} object(s):")
                for obj in objects[:10]:  # Show first 10 objects
                    print(f"   - {obj['Key']} (Size: {obj['Size']} bytes, Modified: {obj['LastModified']})")
                if len(objects) > 10:
                    print(f"   ... and {len(objects) - 10} more objects")
            else:
                print(f"   ⚠ Bucket is empty (no objects found)")
        except ClientError as e:
            print(f"   ✗ Error listing objects: {e}")
        
        # Test 5: Check public accessibility (anonymous access)
        print("\n5. Testing public accessibility...")
        try:
            # Try to access bucket without credentials using unsigned signature
            from botocore import UNSIGNED
            anonymous_s3 = boto3.client(
                's3',
                endpoint_url=endpoint_url,
                config=Config(signature_version=UNSIGNED),
                region_name='us-east-1'
            )
            
            try:
                anonymous_s3.head_bucket(Bucket=bucket_name)
                print(f"   ✓ Bucket is publicly accessible (no authentication required)")
                
                # Try to list objects anonymously
                try:
                    anonymous_response = anonymous_s3.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
                    print(f"   ✓ Public listing of objects is allowed")
                except ClientError as list_error:
                    print(f"   ⚠ Public bucket access is allowed but listing objects is denied")
                    
            except ClientError as e:
                error_code = int(e.response['Error']['Code'])
                if error_code == 403:
                    print(f"   ✓ Bucket is NOT publicly accessible (authentication required)")
                else:
                    print(f"   ⚠ Unexpected error during public access test: {e}")
        except Exception as e:
            print(f"   ✗ Error during public accessibility test: {e}")
        
        # Test 6: Check bucket versioning
        print("\n6. Checking bucket versioning...")
        try:
            versioning = s3_client.get_bucket_versioning(Bucket=bucket_name)
            status = versioning.get('Status', 'Disabled')
            mfa_delete = versioning.get('MFADelete', 'Disabled')
            print(f"   Versioning: {status}")
            print(f"   MFA Delete: {mfa_delete}")
        except ClientError as e:
            print(f"   ✗ Error checking bucket versioning: {e}")
        
        # Test 7: Check bucket encryption
        print("\n7. Checking bucket encryption...")
        try:
            encryption = s3_client.get_bucket_encryption(Bucket=bucket_name)
            rules = encryption.get('ServerSideEncryptionConfiguration', {}).get('Rules', [])
            if rules:
                print(f"   ✓ Server-side encryption is enabled:")
                for rule in rules:
                    sse_algo = rule.get('ApplyServerSideEncryptionByDefault', {}).get('SSEAlgorithm')
                    print(f"   - Algorithm: {sse_algo}")
            else:
                print(f"   ⚠ No encryption configuration found")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ServerSideEncryptionConfigurationNotFoundError':
                print(f"   ⚠ No server-side encryption configured")
            else:
                print(f"   ✗ Error checking bucket encryption: {e}")
        
        # Test 8: Check CORS configuration
        print("\n8. Checking CORS configuration...")
        try:
            cors = s3_client.get_bucket_cors(Bucket=bucket_name)
            cors_rules = cors.get('CORSRules', [])
            if cors_rules:
                print(f"   ✓ CORS is configured with {len(cors_rules)} rule(s)")
                for i, rule in enumerate(cors_rules, 1):
                    print(f"   Rule {i}:")
                    print(f"   - Allowed methods: {rule.get('AllowedMethods', [])}")
                    print(f"   - Allowed origins: {rule.get('AllowedOrigins', [])}")
            else:
                print(f"   ⚠ No CORS configuration found")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchCORSConfiguration':
                print(f"   ⚠ No CORS configuration found")
            else:
                print(f"   ✗ Error checking CORS configuration: {e}")
        
        print("\n" + "=" * 60)
        print("Bucket Test Complete")
        print("=" * 60)
        
    except EndpointConnectionError as e:
        print(f"\n✗ Connection Error: Cannot connect to MinIO server at {endpoint_url}")
        print(f"  Please ensure MinIO server is running and accessible.")
        print(f"  Error details: {e}")
    except Exception as e:
        print(f"\n✗ Unexpected error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_minio_bucket()
