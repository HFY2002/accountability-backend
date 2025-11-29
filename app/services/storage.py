import boto3
from botocore.client import Config
from app.core.config import settings

class StorageService:
    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )

    def generate_presigned_put(self, object_name: str, content_type: str) -> str:
        """Generate a URL for the frontend to upload directly to storage."""
        try:
            response = self.s3_client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": settings.PROOF_BUCKET,
                    "Key": object_name,
                    "ContentType": content_type,
                },
                ExpiresIn=3600,
            )
            return response
        except Exception as e:
            print(f"Error generating presigned URL: {e}")
            return None

    def generate_presigned_get(self, object_name: str, expires_in: int = 3600) -> str:
        """Generate temporary access URL for authorized users (private access)."""
        try:
            response = self.s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": settings.PROOF_BUCKET,
                    "Key": object_name,
                },
                ExpiresIn=expires_in,
            )
            return response
        except Exception as e:
            print(f"Error generating presigned get URL: {e}")
            return None

    def get_public_url(self, object_name: str) -> str:
        """Generate a viewable URL (assuming public read or proxy)."""
        return f"http://{settings.MINIO_ENDPOINT}/{settings.PROOF_BUCKET}/{object_name}"
    
    def get_object_key_from_url(self, url: str) -> str:
        """Extract object key from full URL."""
        # Handle both full URLs and relative paths
        if '/' in url:
            return url.split('/')[-1]
        return url

storage_service = StorageService()