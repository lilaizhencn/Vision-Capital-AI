import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    files = relationship("ProjectFile", back_populates="project", cascade="all, delete-orphan")

