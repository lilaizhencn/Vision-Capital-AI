import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EvidenceStatus(str, enum.Enum):
    missing = "missing"
    partial = "partial"
    covered = "covered"


class ResearchSourceStatus(str, enum.Enum):
    discovered = "discovered"
    ingested = "ingested"
    review_required = "review_required"
    failed = "failed"


class EvidenceRequirement(Base):
    __tablename__ = "evidence_requirements"
    __table_args__ = (UniqueConstraint("project_id", "category", name="uq_evidence_requirement_project_category"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[EvidenceStatus] = mapped_column(Enum(EvidenceStatus, name="evidence_status"), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    suggested_document: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ResearchSource(Base):
    __tablename__ = "research_sources"
    __table_args__ = (UniqueConstraint("project_id", "url_hash", name="uq_research_source_project_url"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    file_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("project_files.id", ondelete="SET NULL"), nullable=True)
    evidence_category: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    publisher: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    snippet: Mapped[str] = mapped_column(Text, default="", nullable=False)
    quality: Mapped[str] = mapped_column(String(32), default="official", nullable=False)
    status: Mapped[ResearchSourceStatus] = mapped_column(
        Enum(ResearchSourceStatus, name="research_source_status"), default=ResearchSourceStatus.discovered, nullable=False
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
