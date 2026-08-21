"""Product media storage abstraction.

Provides LocalStorage (dev) and S3Storage (production) implementations.
All file operations are tenant-scoped via storage prefixes.
"""

from __future__ import annotations

import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO

from app.config import get_settings

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_VIDEO_TYPES = {"video/mp4"}
ALLOWED_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_VIDEO_TYPES
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


class StorageError(Exception):
    pass


class BaseStorage(ABC):
    @abstractmethod
    def put(self, tenant_id: int, product_id: int, filename: str, data: BinaryIO, content_type: str) -> str:
        """Store file and return public URL."""
        ...

    @abstractmethod
    def delete(self, tenant_id: int, product_id: int, filename: str) -> None:
        """Delete file."""
        ...

    def _key(self, tenant_id: int, product_id: int, filename: str) -> str:
        return f"media/{tenant_id}/{product_id}/{filename}"


class LocalStorage(BaseStorage):
    def __init__(self, base_path: str | None = None):
        settings = get_settings()
        self.base_path = Path(base_path or getattr(settings, "MEDIA_ROOT", "./media"))
        self.base_path.mkdir(parents=True, exist_ok=True)

    def put(self, tenant_id: int, product_id: int, filename: str, data: BinaryIO, content_type: str) -> str:
        key = self._key(tenant_id, product_id, filename)
        full_path = self.base_path / key
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "wb") as f:
            while chunk := data.read(8192):
                f.write(chunk)
        return f"/media/{key}"

    def delete(self, tenant_id: int, product_id: int, filename: str) -> None:
        key = self._key(tenant_id, product_id, filename)
        full_path = self.base_path / key
        if full_path.exists():
            full_path.unlink()


class S3Storage(BaseStorage):
    def __init__(self):
        settings = get_settings()
        self.bucket = getattr(settings, "S3_BUCKET", "media")
        self.endpoint_url = getattr(settings, "S3_ENDPOINT_URL", None)
        self.region = getattr(settings, "S3_REGION", "us-east-1")
        self.access_key = getattr(settings, "AWS_ACCESS_KEY_ID", "")
        self.secret_key = getattr(settings, "AWS_SECRET_ACCESS_KEY", "")

    def _client(self):
        import boto3
        kwargs = {"region_name": self.region}
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        if self.access_key:
            kwargs["aws_access_key_id"] = self.access_key
            kwargs["aws_secret_access_key"] = self.secret_key
        return boto3.client("s3", **kwargs)

    def put(self, tenant_id: int, product_id: int, filename: str, data: BinaryIO, content_type: str) -> str:
        key = self._key(tenant_id, product_id, filename)
        client = self._client()
        client.upload_fileobj(data, self.bucket, key, ExtraArgs={"ContentType": content_type})
        if self.endpoint_url:
            return f"{self.endpoint_url}/{self.bucket}/{key}"
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"

    def delete(self, tenant_id: int, product_id: int, filename: str) -> None:
        key = self._key(tenant_id, product_id, filename)
        client = self._client()
        client.delete_object(Bucket=self.bucket, Key=key)


def get_storage() -> BaseStorage:
    settings = get_settings()
    storage_type = getattr(settings, "STORAGE_TYPE", "local")
    if storage_type == "s3":
        return S3Storage()
    return LocalStorage()
