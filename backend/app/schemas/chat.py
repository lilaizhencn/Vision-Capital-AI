from datetime import datetime

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


class Citation(BaseModel):
    file_id: str
    filename: str
    content: str


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]


class ChatMessageRead(BaseModel):
    id: str
    project_id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}

