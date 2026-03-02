"""S3/R2 storage backend — implements StorageBackend Protocol."""

import boto3
from botocore.config import Config

from app.config import settings


class S3StorageBackend:
    """Concrete StorageBackend using S3-compatible APIs (AWS S3 or Cloudflare R2)."""

    def __init__(self) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
            config=Config(signature_version="s3v4"),
        )
        self._bucket = settings.s3_bucket_name

    async def upload(
        self, *, file_data: bytes, key: str, content_type: str,
    ) -> str:
        """Upload a file to S3/R2. Returns the public URL."""
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=file_data,
            ContentType=content_type,
        )
        return self.get_public_url(key)

    async def delete(self, *, key: str) -> None:
        """Delete a file from S3/R2."""
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def get_public_url(self, key: str) -> str:
        """Build the public URL for a stored object."""
        if settings.s3_endpoint_url:
            return f"{settings.s3_endpoint_url}/{self._bucket}/{key}"
        return f"https://{self._bucket}.s3.{settings.s3_region}.amazonaws.com/{key}"


_storage_instance: S3StorageBackend | None = None


def get_storage() -> S3StorageBackend:
    """Singleton accessor for the storage backend."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = S3StorageBackend()
    return _storage_instance
