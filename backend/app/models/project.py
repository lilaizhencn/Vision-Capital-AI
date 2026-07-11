import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class InvestmentStatus(str, enum.Enum):
    pre_investment = "pre_investment"
    in_progress = "in_progress"
    post_investment = "post_investment"
    rejected = "rejected"
    exited = "exited"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    company_name: Mapped[str] = mapped_column(String(200))
    industry: Mapped[str] = mapped_column(String(120))
    stage: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    investment_status: Mapped[InvestmentStatus] = mapped_column(
        Enum(InvestmentStatus, name="investment_status"),
        default=InvestmentStatus.pre_investment,
        nullable=False,
    )
    research_auto_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    research_status: Mapped[str] = mapped_column(String(20), default="idle", nullable=False)
    last_research_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_research_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    research_last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    files = relationship("ProjectFile", back_populates="project", cascade="all, delete-orphan")
