from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str


class Citation(BaseModel):
    file_id: str
    filename: str
    content: str
    source_kind: str = "upload"
    source_url: str | None = None
    source_quality: str | None = None
    document_role: str = "uploaded_evidence"


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    confidence: str
    missing_evidence: list[str]
    evidence_control_passed: bool | None = None
    quality_issues: list[str] = Field(default_factory=list)


class ChatMessageRead(BaseModel):
    id: str
    project_id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}
