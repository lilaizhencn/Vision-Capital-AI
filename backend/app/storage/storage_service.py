from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import boto3
from botocore.client import Config

from app.core.config import settings


@dataclass
class StoredFile:
    bucket: str | None
    object_key: str


class LocalStorageService:
    def __init__(self) -> None:
        self.base_path = settings.local_storage_absolute_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    def upload_file(self, object_key: str, content: bytes, content_type: str | None = None) -> StoredFile:
        path = self.base_path / object_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return StoredFile(bucket=None, object_key=object_key)

    def download_file(self, object_key: str) -> bytes:
        return (self.base_path / object_key).read_bytes()

    def delete_file(self, object_key: str) -> None:
        path = self.base_path / object_key
        if path.exists():
            path.unlink()

    def generate_presigned_url(self, object_key: str) -> str:
        return str((self.base_path / object_key).resolve())


class R2StorageService:
    def __init__(self) -> None:
        self.bucket = settings.r2_bucket_name
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )

    def upload_file(self, object_key: str, content: bytes, content_type: str | None = None) -> StoredFile:
        extra_args = {"ContentType": content_type} if content_type else {}
        self.client.put_object(Bucket=self.bucket, Key=object_key, Body=content, **extra_args)
        return StoredFile(bucket=self.bucket, object_key=object_key)

    def download_file(self, object_key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=object_key)
        return response["Body"].read()

    def delete_file(self, object_key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=object_key)

    def generate_presigned_url(self, object_key: str) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": object_key},
            ExpiresIn=3600,
        )


def get_storage_service() -> R2StorageService | LocalStorageService:
    # R2 未配置时回退到本地存储，方便本地学习和联调。
    return R2StorageService() if settings.r2_enabled else LocalStorageService()

