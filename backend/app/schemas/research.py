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


class RequirementFieldRead(BaseModel):
    key: str
    label: str
    status: str
    evidence_excerpt: str = ""
    source_file_id: str | None = None
    source_filename: str | None = None


class RequirementFileRead(BaseModel):
    id: str
    filename: str
    content_type: str
    parse_status: str
    source_kind: str
    created_at: datetime


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
    auto_enabled: bool = True
    status: str = "idle"
    last_research_at: datetime | None = None
    next_research_at: datetime | None = None
    last_error: str | None = None


class RequirementDetailRead(BaseModel):
    requirement: EvidenceRequirementRead
    fields: list[RequirementFieldRead]
    related_files: list[RequirementFileRead]
    related_sources: list[ResearchSourceRead]


class ResearchSettingsUpdate(BaseModel):
    auto_enabled: bool


class EnrichmentResponse(BaseModel):
    status: str
    task_id: str | None = None
