from datetime import datetime

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


class Citation(BaseModel):
    file_id: str
    filename: str
    content: str
    source_kind: str = "upload"
    source_url: str | None = None
    source_quality: str | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    confidence: str
    missing_evidence: list[str]
    evidence_control_passed: bool | None = None


class ChatMessageRead(BaseModel):
    id: str
    project_id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}
