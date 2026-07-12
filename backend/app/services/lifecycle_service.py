import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.file import ParseStatus, ProjectFile
from app.models.lifecycle import (
    DataSourceSubscription,
    InvestmentOpinionVersion,
    MonitoringMetric,
    MonitoringObservation,
    RiskEvent,
    TransactionExecution,
)
from app.models.project import InvestmentStatus, Project
from app.models.research import EvidenceRequirement, EvidenceStatus, ResearchSource, ResearchSourceStatus
from app.schemas.lifecycle import (
    DataSourceSubscriptionCreate,
    MonitoringMetricCreate,
    MonitoringObservationCreate,
    RiskEventCreate,
    RiskEventUpdate,
    TransactionExecutionWrite,
)


class LifecycleService:
    """Enforce investment-stage gates and preserve append-only decision baselines."""

    def __init__(self, db: Session):
        self.db = db

    def project(self, project_id: str, owner_id: str) -> Project:
        project = self.db.scalar(select(Project).where(Project.id == project_id, Project.owner_id == owner_id))
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return project

    def summary(self, project_id: str, owner_id: str) -> dict:
        self.project(project_id, owner_id)
        return {
            "transaction": self.db.scalar(select(TransactionExecution).where(TransactionExecution.project_id == project_id)),
            "metrics": list(self.db.scalars(select(MonitoringMetric).where(
                MonitoringMetric.project_id == project_id
            ).order_by(MonitoringMetric.created_at))),
            "observations": list(self.db.scalars(select(MonitoringObservation).where(
                MonitoringObservation.project_id == project_id
            ).order_by(MonitoringObservation.period_end.desc()).limit(200))),
            "risks": list(self.db.scalars(select(RiskEvent).where(
                RiskEvent.project_id == project_id
            ).order_by(RiskEvent.detected_at.desc()).limit(100))),
            "opinions": self.opinions(project_id, owner_id),
            "data_sources": list(self.db.scalars(select(DataSourceSubscription).where(
                DataSourceSubscription.project_id == project_id
            ).order_by(DataSourceSubscription.created_at.desc()))),
        }

    def upsert_transaction(
        self, project_id: str, owner_id: str, payload: TransactionExecutionWrite
    ) -> TransactionExecution:
        project = self.project(project_id, owner_id)
        self._validate_file_ids(project_id, payload.evidence_file_ids)
        condition_file_ids = [item.evidence_file_id for item in payload.conditions_precedent if item.evidence_file_id]
        self._validate_file_ids(project_id, condition_file_ids)
        if payload.status == "closed":
            incomplete = [item.label for item in payload.conditions_precedent if item.status not in {"satisfied", "waived"}]
            if payload.approval_status != "approved":
                raise HTTPException(status_code=400, detail="IC approval is required before closing")
            if incomplete:
                raise HTTPException(status_code=400, detail=f"Unresolved closing conditions: {', '.join(incomplete)}")
            if not payload.evidence_file_ids:
                raise HTTPException(status_code=400, detail="Closing requires at least one signed evidence file")
        item = self.db.scalar(select(TransactionExecution).where(TransactionExecution.project_id == project_id))
        if not item:
            item = TransactionExecution(project_id=project_id)
            self.db.add(item)
        values = payload.model_dump(mode="json")
        for key, value in values.items():
            setattr(item, key, value)
        item.approved_at = (
            item.approved_at or datetime.now(timezone.utc)
            if payload.approval_status == "approved" else None
        )
        if payload.status in {"signing", "closing"}:
            project.investment_status = InvestmentStatus.in_progress
        elif payload.status == "closed":
            project.investment_status = InvestmentStatus.post_investment
        self.db.commit()
        self.db.refresh(item)
        self.refresh_opinion(project_id, owner_id)
        return item

    def create_metric(self, project_id: str, owner_id: str, payload: MonitoringMetricCreate) -> MonitoringMetric:
        self.project(project_id, owner_id)
        item = MonitoringMetric(project_id=project_id, **payload.model_dump())
        self.db.add(item)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(status_code=409, detail="Metric code already exists for this project") from exc
        self.db.refresh(item)
        return item

    def create_observation(
        self, project_id: str, metric_id: str, owner_id: str, payload: MonitoringObservationCreate
    ) -> MonitoringObservation:
        self.project(project_id, owner_id)
        metric = self.db.scalar(select(MonitoringMetric).where(
            MonitoringMetric.id == metric_id, MonitoringMetric.project_id == project_id
        ))
        if not metric:
            raise HTTPException(status_code=404, detail="Monitoring metric not found")
        self._validate_file_ids(project_id, [payload.source_file_id] if payload.source_file_id else [])
        status = self._metric_status(metric, payload.value)
        variance = payload.value - metric.target_value if metric.target_value is not None else None
        observation = MonitoringObservation(
            project_id=project_id,
            metric_id=metric_id,
            status=status,
            variance_from_target=variance,
            **payload.model_dump(),
        )
        self.db.add(observation)
        try:
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(status_code=409, detail="An observation already exists for this metric and period") from exc
        if status in {"watch", "high"}:
            self.db.add(RiskEvent(
                project_id=project_id,
                observation_id=observation.id,
                category="kpi_threshold",
                title=f"{metric.name}触发{('高风险' if status == 'high' else '关注')}阈值",
                severity=status,
                description=f"{payload.period_end.isoformat()} 观测值 {payload.value} {metric.unit}，需按已批准阈值复核。",
                trigger_source=f"monitoring_metric:{metric.code}",
                evidence_file_ids=[payload.source_file_id] if payload.source_file_id else [],
            ))
        self.db.commit()
        self.db.refresh(observation)
        self.refresh_opinion(project_id, owner_id)
        return observation

    def create_risk(self, project_id: str, owner_id: str, payload: RiskEventCreate) -> RiskEvent:
        self.project(project_id, owner_id)
        self._validate_file_ids(project_id, payload.evidence_file_ids)
        item = RiskEvent(project_id=project_id, **payload.model_dump())
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        self.refresh_opinion(project_id, owner_id)
        return item

    def update_risk(self, project_id: str, risk_id: str, owner_id: str, payload: RiskEventUpdate) -> RiskEvent:
        self.project(project_id, owner_id)
        item = self.db.scalar(select(RiskEvent).where(RiskEvent.id == risk_id, RiskEvent.project_id == project_id))
        if not item:
            raise HTTPException(status_code=404, detail="Risk event not found")
        item.status = payload.status
        if payload.description is not None:
            item.description = payload.description
        item.resolved_at = datetime.now(timezone.utc) if payload.status == "resolved" else None
        self.db.commit()
        self.db.refresh(item)
        self.refresh_opinion(project_id, owner_id)
        return item

    def create_data_source(
        self, project_id: str, owner_id: str, payload: DataSourceSubscriptionCreate
    ) -> DataSourceSubscription:
        self.project(project_id, owner_id)
        url = str(payload.url)
        from app.services.research_service import ResearchService
        ResearchService._validate_configured_public_url(url)
        item = DataSourceSubscription(
            project_id=project_id,
            name=payload.name,
            source_type=payload.source_type,
            category=payload.category,
            url=url,
            cadence_hours=payload.cadence_hours,
            active=payload.active,
            status="scheduled" if payload.active else "paused",
            next_run_at=datetime.now(timezone.utc) if payload.active else None,
        )
        self.db.add(item)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(status_code=409, detail="This data source is already subscribed") from exc
        self.db.refresh(item)
        return item

    def update_data_source(self, project_id: str, source_id: str, owner_id: str, values: dict) -> DataSourceSubscription:
        self.project(project_id, owner_id)
        item = self.db.scalar(select(DataSourceSubscription).where(
            DataSourceSubscription.id == source_id, DataSourceSubscription.project_id == project_id
        ))
        if not item:
            raise HTTPException(status_code=404, detail="Data source subscription not found")
        for key, value in values.items():
            setattr(item, key, value)
        item.status = "scheduled" if item.active else "paused"
        item.next_run_at = datetime.now(timezone.utc) if item.active else None
        self.db.commit()
        self.db.refresh(item)
        return item

    def run_data_source(self, subscription_id: str, owner_id: str) -> ProjectFile:
        subscription = self.db.scalar(select(DataSourceSubscription).where(DataSourceSubscription.id == subscription_id))
        if not subscription:
            raise HTTPException(status_code=404, detail="Data source subscription not found")
        project = self.project(subscription.project_id, owner_id)
        from app.services.research_service import ResearchService
        source = ResearchSource(
            project_id=project.id,
            evidence_category=subscription.category,
            title=subscription.name,
            publisher=urlparse(subscription.url).hostname or "configured source",
            domain=(urlparse(subscription.url).hostname or "").lower(),
            url=subscription.url,
            url_hash=hashlib.sha256(f"{subscription.url}:{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest(),
            snippet="Configured continuous data source",
            quality="configured",
            status=ResearchSourceStatus.discovered,
        )
        self.db.add(source)
        self.db.commit()
        try:
            file = ResearchService(self.db)._download_and_store(project, owner_id, source, allow_configured_source=True)
            source.file_id = file.id
            source.status = ResearchSourceStatus.ingested
            source.fetched_at = datetime.now(timezone.utc)
            subscription.status = "ingested"
            subscription.last_run_at = source.fetched_at
            subscription.next_run_at = source.fetched_at + timedelta(hours=subscription.cadence_hours)
            subscription.last_error = None
            self.db.commit()
            from app.workers.tasks import parse_uploaded_file_task
            parse_uploaded_file_task.delay(file.id)
            return file
        except Exception as exc:
            source.status = ResearchSourceStatus.failed
            source.error = str(exc)[:2000]
            subscription.status = "failed"
            subscription.last_run_at = datetime.now(timezone.utc)
            subscription.next_run_at = subscription.last_run_at + timedelta(hours=subscription.cadence_hours)
            subscription.last_error = str(exc)[:2000]
            self.db.commit()
            raise

    def opinions(self, project_id: str, owner_id: str) -> list[InvestmentOpinionVersion]:
        self.project(project_id, owner_id)
        return list(self.db.scalars(select(InvestmentOpinionVersion).where(
            InvestmentOpinionVersion.project_id == project_id
        ).order_by(InvestmentOpinionVersion.version.desc()).limit(20)))

    def refresh_opinion(self, project_id: str, owner_id: str) -> InvestmentOpinionVersion:
        project = self.project(project_id, owner_id)
        files = list(self.db.scalars(select(ProjectFile).where(
            ProjectFile.project_id == project_id, ProjectFile.parse_status == ParseStatus.completed
        ).order_by(ProjectFile.created_at)))
        requirements = list(self.db.scalars(select(EvidenceRequirement).where(EvidenceRequirement.project_id == project_id)))
        transaction = self.db.scalar(select(TransactionExecution).where(TransactionExecution.project_id == project_id))
        observations = list(self.db.scalars(select(MonitoringObservation).where(
            MonitoringObservation.project_id == project_id
        ).order_by(MonitoringObservation.period_end.desc()).limit(100)))
        risks = list(self.db.scalars(select(RiskEvent).where(
            RiskEvent.project_id == project_id, RiskEvent.status != "resolved"
        )))
        evidence_payload = {
            "files": [(item.id, item.checksum_sha256, item.created_at.isoformat()) for item in files],
            "requirements": [(item.category, item.status.value) for item in requirements],
            "transaction": None if not transaction else {
                "status": transaction.status,
                "approval": transaction.approval_status,
                "conditions": transaction.conditions_precedent,
            },
            "observations": [(item.metric_id, item.period_end.isoformat(), str(item.value), item.status) for item in observations],
            "risks": [(item.id, item.severity, item.status) for item in risks],
        }
        evidence_hash = hashlib.sha256(json.dumps(evidence_payload, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
        latest = self.db.scalar(select(InvestmentOpinionVersion).where(
            InvestmentOpinionVersion.project_id == project_id
        ).order_by(InvestmentOpinionVersion.version.desc()))
        if latest and latest.evidence_hash == evidence_hash:
            return latest
        covered = sum(item.status == EvidenceStatus.covered for item in requirements)
        coverage = covered / max(len(requirements), 1)
        high_risks = sum(item.severity in {"high", "critical"} for item in risks)
        watch_risks = sum(item.severity == "watch" for item in risks)
        source_count = len(files)
        quality = min(100, round(coverage * 55 + min(source_count, 10) * 3 + min(len(observations), 15) * 1, 2))
        if project.investment_status == InvestmentStatus.in_progress:
            gates_ready = bool(transaction and transaction.approval_status == "approved" and all(
                condition.get("status") in {"satisfied", "waived"}
                for condition in transaction.conditions_precedent
            ))
            recommendation = "hold_execution" if high_risks or not gates_ready else "proceed_with_controls"
        elif project.investment_status == InvestmentStatus.post_investment:
            recommendation = "escalate" if high_risks else "enhanced_monitoring" if watch_risks else "monitor"
        else:
            recommendation = "proceed_to_diligence" if coverage >= 0.75 and source_count >= 2 else "insufficient_evidence"
        confidence = "high" if quality >= 80 else "medium" if quality >= 55 else "low"
        thesis = (
            f"截至本版本，已核验 {source_count} 份资料，{covered}/{len(requirements)} 个研究维度达到覆盖标准；"
            f"记录 {len(observations)} 个周期观测，存在 {high_risks} 个高风险和 {watch_risks} 个关注事件。"
            "本结论是证据门禁下的决策基线，不构成脱离投委授权、估值模型和原始凭证的交易建议。"
        )
        previous = latest.recommendation if latest else "无历史版本"
        change_summary = f"证据集发生变化；建议由“{previous}”更新为“{recommendation}”。"
        opinion = InvestmentOpinionVersion(
            project_id=project_id,
            version=(latest.version + 1 if latest else 1),
            stage=project.investment_status.value,
            recommendation=recommendation,
            confidence=confidence,
            quality_score=Decimal(str(quality)),
            thesis=thesis,
            change_summary=change_summary,
            evidence_hash=evidence_hash,
            evidence_file_ids=[item.id for item in files],
            source_count=source_count,
        )
        self.db.add(opinion)
        self.db.commit()
        self.db.refresh(opinion)
        return opinion

    def _validate_file_ids(self, project_id: str, file_ids: list[str]) -> None:
        unique_ids = list(dict.fromkeys(file_ids))
        count = len(list(self.db.scalars(select(ProjectFile.id).where(
            ProjectFile.project_id == project_id, ProjectFile.id.in_(unique_ids)
        )))) if unique_ids else 0
        if count != len(unique_ids):
            raise HTTPException(status_code=400, detail="Every evidence file must belong to this project")

    @staticmethod
    def _metric_status(metric: MonitoringMetric, value: Decimal) -> str:
        if metric.breach_threshold is not None:
            breached = value < metric.breach_threshold if metric.direction == "higher_better" else value > metric.breach_threshold
            if breached:
                return "high"
        if metric.watch_threshold is not None:
            watched = value < metric.watch_threshold if metric.direction == "higher_better" else value > metric.watch_threshold
            if watched:
                return "watch"
        return "normal"
