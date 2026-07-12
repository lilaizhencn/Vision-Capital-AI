from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, HttpUrl, model_validator


class ConditionPrecedent(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=255)
    status: str = Field(default="pending", pattern=r"^(pending|satisfied|waived|failed)$")
    owner: str = Field(default="", max_length=120)
    due_date: date | None = None
    evidence_file_id: str | None = None
    waiver_reason: str = Field(default="", max_length=2000)


class TransactionExecutionWrite(BaseModel):
    transaction_type: str = Field(default="equity", pattern=r"^(equity|debt|convertible|fund|secondary|other)$")
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    committed_amount: Decimal | None = Field(default=None, gt=0)
    entry_valuation: Decimal | None = Field(default=None, gt=0)
    ownership_pct: Decimal | None = Field(default=None, ge=0, le=100)
    status: str = Field(default="drafting", pattern=r"^(drafting|ic_review|signing|closing|closed|aborted)$")
    approval_status: str = Field(default="pending", pattern=r"^(pending|conditional|approved|rejected)$")
    decision_rationale: str = Field(default="", max_length=20_000)
    conditions_precedent: list[ConditionPrecedent] = Field(default_factory=list, max_length=100)
    evidence_file_ids: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_decision(self):
        if self.approval_status != "pending" and len(self.decision_rationale.strip()) < 20:
            raise ValueError("A documented investment committee rationale of at least 20 characters is required")
        return self


class TransactionExecutionRead(TransactionExecutionWrite):
    id: str
    project_id: str
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MonitoringMetricCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1, max_length=120)
    unit: str = Field(default="", max_length=40)
    frequency: str = Field(default="monthly", pattern=r"^(weekly|monthly|quarterly|annual|event)$")
    direction: str = Field(default="higher_better", pattern=r"^(higher_better|lower_better)$")
    baseline_value: Decimal | None = None
    target_value: Decimal | None = None
    watch_threshold: Decimal | None = None
    breach_threshold: Decimal | None = None
    owner: str = Field(default="", max_length=120)
    source_description: str = Field(default="", max_length=500)
    active: bool = True

    @model_validator(mode="after")
    def validate_threshold_order(self):
        if self.watch_threshold is None or self.breach_threshold is None:
            return self
        invalid = (
            self.direction == "higher_better" and self.breach_threshold > self.watch_threshold
        ) or (
            self.direction == "lower_better" and self.breach_threshold < self.watch_threshold
        )
        if invalid:
            raise ValueError("Breach threshold must represent a worse outcome than the watch threshold")
        return self


class MonitoringMetricRead(MonitoringMetricCreate):
    id: str
    project_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MonitoringObservationCreate(BaseModel):
    period_end: date
    value: Decimal
    source_file_id: str | None = None
    note: str = Field(default="", max_length=5000)


class MonitoringObservationRead(MonitoringObservationCreate):
    id: str
    project_id: str
    metric_id: str
    status: str
    variance_from_target: Decimal | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RiskEventCreate(BaseModel):
    category: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    severity: str = Field(default="watch", pattern=r"^(watch|high|critical)$")
    status: str = Field(default="open", pattern=r"^(open|monitoring|resolved)$")
    description: str = Field(default="", max_length=20_000)
    trigger_source: str = Field(default="manual", max_length=500)
    evidence_file_ids: list[str] = Field(default_factory=list, max_length=100)


class RiskEventUpdate(BaseModel):
    status: str = Field(pattern=r"^(open|monitoring|resolved)$")
    description: str | None = Field(default=None, max_length=20_000)


class RiskEventRead(RiskEventCreate):
    id: str
    project_id: str
    observation_id: str | None
    detected_at: datetime
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InvestmentOpinionRead(BaseModel):
    id: str
    project_id: str
    version: int
    stage: str
    recommendation: str
    confidence: str
    quality_score: Decimal
    thesis: str
    change_summary: str
    evidence_hash: str
    evidence_file_ids: list[str]
    source_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DataSourceSubscriptionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source_type: str = Field(pattern=r"^(official_filing|regulator|company_ir|industry_data|news|other)$")
    category: str = Field(pattern=r"^(business|financial|market|competition|team|legal|customers|valuation)$")
    url: HttpUrl
    cadence_hours: int = Field(default=168, ge=1, le=8760)
    active: bool = True


class DataSourceSubscriptionUpdate(BaseModel):
    cadence_hours: int | None = Field(default=None, ge=1, le=8760)
    active: bool | None = None


class DataSourceSubscriptionRead(BaseModel):
    id: str
    project_id: str
    name: str
    source_type: str
    category: str
    url: str
    cadence_hours: int
    active: bool
    status: str
    last_run_at: datetime | None
    next_run_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LifecycleSummary(BaseModel):
    transaction: TransactionExecutionRead | None
    metrics: list[MonitoringMetricRead]
    observations: list[MonitoringObservationRead]
    risks: list[RiskEventRead]
    opinions: list[InvestmentOpinionRead]
    data_sources: list[DataSourceSubscriptionRead]
