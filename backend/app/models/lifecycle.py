import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TransactionExecution(Base):
    __tablename__ = "transaction_executions"
    __table_args__ = (UniqueConstraint("project_id", name="uq_transaction_execution_project"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    transaction_type: Mapped[str] = mapped_column(String(32), default="equity", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="CNY", nullable=False)
    committed_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    entry_valuation: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    ownership_pct: Mapped[Decimal | None] = mapped_column(Numeric(9, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="drafting", nullable=False)
    approval_status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    decision_rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    conditions_precedent: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    evidence_file_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class MonitoringMetric(Base):
    __tablename__ = "monitoring_metrics"
    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_monitoring_metric_project_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), default="monthly", nullable=False)
    direction: Mapped[str] = mapped_column(String(20), default="higher_better", nullable=False)
    baseline_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    target_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    watch_threshold: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    breach_threshold: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    owner: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    source_description: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class MonitoringObservation(Base):
    __tablename__ = "monitoring_observations"
    __table_args__ = (UniqueConstraint("metric_id", "period_end", name="uq_monitoring_observation_period"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    metric_id: Mapped[str] = mapped_column(String(36), ForeignKey("monitoring_metrics.id", ondelete="CASCADE"), index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)
    variance_from_target: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    source_file_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("project_files.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RiskEvent(Base):
    __tablename__ = "risk_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    observation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("monitoring_observations.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="watch", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    trigger_source: Mapped[str] = mapped_column(String(500), default="manual", nullable=False)
    evidence_file_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class InvestmentOpinionVersion(Base):
    __tablename__ = "investment_opinion_versions"
    __table_args__ = (UniqueConstraint("project_id", "version", name="uq_investment_opinion_project_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    recommendation: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    quality_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    thesis: Mapped[str] = mapped_column(Text, nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    evidence_file_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DataSourceSubscription(Base):
    __tablename__ = "data_source_subscriptions"
    __table_args__ = (UniqueConstraint("project_id", "url", name="uq_data_source_subscription_project_url"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    cadence_hours: Mapped[int] = mapped_column(Integer, default=168, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
