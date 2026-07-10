import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MonitoringUpdate(Base):
    __tablename__ = "monitoring_updates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    metric_name: Mapped[str] = mapped_column(String(120))
    metric_value: Mapped[str] = mapped_column(String(120))
    metric_unit: Mapped[str] = mapped_column(String(40), default="")
    risk_level: Mapped[str] = mapped_column(String(20), default="normal")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
