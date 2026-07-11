from datetime import datetime

from pydantic import BaseModel

from app.models.research import EvidenceStatus, ResearchSourceStatus


class EvidenceRequirementRead(BaseModel):
    id: str
    project_id: str
    category: str
    label: str
    status: EvidenceStatus
    priority: str
    reason: str
    suggested_document: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResearchSourceRead(BaseModel):
    id: str
    project_id: str
    file_id: str | None
    evidence_category: str
    title: str
    publisher: str
    domain: str
    url: str
    snippet: str
    quality: str
    status: ResearchSourceStatus
    error: str | None
    discovered_at: datetime
    fetched_at: datetime | None

    model_config = {"from_attributes": True}


class ResearchWorkspaceRead(BaseModel):
    requirements: list[EvidenceRequirementRead]
    sources: list[ResearchSourceRead]
    enrichment_running: bool = False


class EnrichmentResponse(BaseModel):
    status: str
    task_id: str | None = None
