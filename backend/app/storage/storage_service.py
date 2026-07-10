from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from pathlib import Path

import boto3
from botocore.client import Config

from app.core.config import settings


@dataclass
class StoredFile:
    bucket: str | None
    object_key: str


@dataclass
class UploadPlan:
    object_key: str
    upload_url: str | None
    upload_mode: str
    part_size: int | None = None
    total_parts: int | None = None
    upload_id: str | None = None


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

    def create_upload_plan(self, object_key: str, size: int, content_type: str) -> UploadPlan:
        # Local fallback keeps the same API contract; the backend receives the file bytes.
        return UploadPlan(object_key, None, "backend", None, None, None)

    def object_exists(self, object_key: str, expected_size: int | None = None) -> bool:
        path = self.base_path / object_key
        return path.exists() and (expected_size is None or path.stat().st_size == expected_size)


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
            ExpiresIn=settings.r2_presigned_url_expiry_seconds,
        )

    def create_upload_plan(self, object_key: str, size: int, content_type: str) -> UploadPlan:
        # Small files use a single signed PUT; large files use S3 multipart upload.
        if size < settings.upload_multipart_threshold_bytes:
            url = self.client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self.bucket, "Key": object_key, "ContentType": content_type},
                ExpiresIn=settings.r2_presigned_url_expiry_seconds,
            )
            return UploadPlan(object_key, url, "direct", None, None, None)
        parts = ceil(size / settings.upload_part_size_bytes)
        upload = self.client.create_multipart_upload(Bucket=self.bucket, Key=object_key, ContentType=content_type)
        upload_id = upload["UploadId"]
        # The upload id is embedded server-side in the object key registry in production.
        # Returning it through the signed URL keeps this starter implementation stateless.
        return UploadPlan(object_key, None, "multipart", settings.upload_part_size_bytes, parts, upload_id)

    def presign_upload_part(self, object_key: str, upload_id: str, part_number: int) -> str:
        return self.client.generate_presigned_url(
            "upload_part",
            Params={"Bucket": self.bucket, "Key": object_key, "UploadId": upload_id, "PartNumber": part_number},
            ExpiresIn=settings.r2_presigned_url_expiry_seconds,
        )

    def object_exists(self, object_key: str, expected_size: int | None = None) -> bool:
        try:
            metadata = self.client.head_object(Bucket=self.bucket, Key=object_key)
            return expected_size is None or metadata.get("ContentLength") == expected_size
        except self.client.exceptions.ClientError:
            return False

    def complete_multipart(self, object_key: str, upload_id: str, parts: list[dict]) -> None:
        self.client.complete_multipart_upload(
            Bucket=self.bucket, Key=object_key, UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )


def get_storage_service() -> R2StorageService | LocalStorageService:
    # R2 未配置时回退到本地存储，方便本地学习和联调。
    return R2StorageService() if settings.r2_enabled else LocalStorageService()
