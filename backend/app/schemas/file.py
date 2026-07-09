from datetime import datetime

from pydantic import BaseModel

from app.models.file import ParseStatus


class FileRead(BaseModel):
    id: str
    project_id: str
    filename: str
    content_type: str
    size: int
    r2_bucket: str | None
    r2_object_key: str
    parse_status: ParseStatus
    parse_error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FileUploadResponse(BaseModel):
    file: FileRead
    task_status: str

