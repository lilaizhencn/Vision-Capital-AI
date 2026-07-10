from datetime import datetime

from pydantic import BaseModel, Field

from app.models.file import BatchStatus, ParseStage, ParseStatus


class FileRead(BaseModel):
    id: str
    project_id: str
    batch_id: str | None = None
    filename: str
    content_type: str
    size: int
    r2_bucket: str | None
    r2_object_key: str
    parse_status: ParseStatus
    parse_error: str | None
    parse_stage: ParseStage
    progress: int
    retry_count: int
    checksum_sha256: str | None
    expected_checksum_sha256: str | None
    virus_scan_status: str
    virus_scan_result: str | None
    extracted_data: dict[str, object] | None
    multipart_upload_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FileUploadResponse(BaseModel):
    file: FileRead
    task_status: str


class BatchFileRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    size: int = Field(ge=0)
    content_type: str = Field(default="application/octet-stream", max_length=150)
    checksum_sha256: str | None = Field(default=None, min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")


class BatchCreateRequest(BaseModel):
    files: list[BatchFileRequest]


class UploadSession(BaseModel):
    file_id: str
    object_key: str
    upload_url: str | None
    upload_mode: str
    part_size: int | None = None
    total_parts: int | None = None
    upload_id: str | None = None


class BatchRead(BaseModel):
    id: str
    project_id: str
    total_files: int
    completed_files: int
    failed_files: int
    progress: int
    status: BatchStatus
    files: list[FileRead]
    upload_sessions: list[UploadSession] = Field(default_factory=list)


class MultipartPart(BaseModel):
    part_number: int
    etag: str


class MultipartCompleteRequest(BaseModel):
    parts: list[MultipartPart] = Field(min_length=1)
