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
        
        # Client for generating public-facing URLs (if different from internal)
        if settings.MINIO_PUBLIC_ENDPOINT:
            self.public_s3_client = boto3.client(
                "s3",
                endpoint_url=f"http://{settings.MINIO_PUBLIC_ENDPOINT}",
                aws_access_key_id=settings.MINIO_ACCESS_KEY,
                aws_secret_access_key=settings.MINIO_SECRET_KEY,
                config=Config(signature_version="s3v4"),
                region_name="us-east-1",
            )
        else:
            self.public_s3_client = self.s3_client

    def generate_presigned_put(self, object_name: str, content_type: str) -> str:
        """Generate a URL for the frontend to upload directly to storage."""
        import logging
        logger = logging.getLogger("backend")
        try:
            endpoint = self.public_s3_client.meta.endpoint_url
            logger.info(f"Generating presigned PUT URL using endpoint: {endpoint}")
            
            response = self.public_s3_client.generate_presigned_url(
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
            logger.error(f"Error generating presigned URL: {e}")
            print(f"Error generating presigned URL: {e}")
            return None

    def generate_presigned_get(self, object_name: str, expires_in: int = 3600) -> str:
        """Generate temporary access URL for authorized users (private access)."""
        try:
            response = self.public_s3_client.generate_presigned_url(
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
        """Return direct permanent URL for public bucket access."""
        # Bucket is already public, return direct URL instead of expiring presigned URL
        endpoint = settings.MINIO_PUBLIC_ENDPOINT or settings.MINIO_ENDPOINT
        return f"http://{endpoint}/{settings.PROOF_BUCKET}/{object_name}"
    
    def get_object_key_from_url(self, url: str) -> str:
        """Extract object key from full URL."""
        # Handle both full URLs and relative paths
        if '/' in url:
            return url.split('/')[-1]
        return url

storage_service = StorageService()
