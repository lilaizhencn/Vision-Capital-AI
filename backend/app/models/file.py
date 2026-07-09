import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ParseStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ProjectFile(Base):
    __tablename__ = "project_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(150))
    size: Mapped[int] = mapped_column(Integer)
    r2_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    r2_object_key: Mapped[str] = mapped_column(String(500), unique=True)
    parse_status: Mapped[ParseStatus] = mapped_column(
        Enum(ParseStatus, name="parse_status"),
        default=ParseStatus.pending,
        nullable=False,
    )
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("Project", back_populates="files")

