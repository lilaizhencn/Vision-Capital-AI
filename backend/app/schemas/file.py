from datetime import datetime

from pydantic import BaseModel

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
    multipart_upload_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FileUploadResponse(BaseModel):
    file: FileRead
    task_status: str


class BatchFileRequest(BaseModel):
    filename: str
    size: int
    content_type: str = "application/octet-stream"


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
    upload_sessions: list[UploadSession] = []


class MultipartPart(BaseModel):
    part_number: int
    etag: str


class MultipartCompleteRequest(BaseModel):
    parts: list[MultipartPart]
