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
        self.refresh_opinion(project_id, owner_id)
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
        all_files = list(self.db.scalars(select(ProjectFile).where(
            ProjectFile.project_id == project_id, ProjectFile.parse_status == ParseStatus.completed
        ).order_by(ProjectFile.created_at)))
        public_file_ids = [item.id for item in all_files if item.source_kind == "public_research"]
        research_sources = {
            item.file_id: item for item in self.db.scalars(select(ResearchSource).where(
                ResearchSource.project_id == project_id, ResearchSource.file_id.in_(public_file_ids)
            ))
        } if public_file_ids else {}
        files = [
            item for item in all_files
            if self._opinion_file_is_admissible(project, item, research_sources.get(item.id))
        ]
        admitted_file_ids = {item.id for item in files}
        excluded_public_count = len(all_files) - len(files)
        requirements = list(self.db.scalars(select(EvidenceRequirement).where(EvidenceRequirement.project_id == project_id)))
        transaction = self.db.scalar(select(TransactionExecution).where(TransactionExecution.project_id == project_id))
        observations = list(self.db.scalars(select(MonitoringObservation).where(
            MonitoringObservation.project_id == project_id
        ).order_by(MonitoringObservation.period_end.desc()).limit(100)))
        metrics = list(self.db.scalars(select(MonitoringMetric).where(
            MonitoringMetric.project_id == project_id, MonitoringMetric.active.is_(True)
        )))
        risks = list(self.db.scalars(select(RiskEvent).where(
            RiskEvent.project_id == project_id, RiskEvent.status != "resolved"
        )))
        evidence_payload = {
            "files": [(item.id, item.checksum_sha256, item.created_at.isoformat()) for item in files],
            "excluded_public_files": [item.id for item in all_files if item.id not in admitted_file_ids],
            "requirements": [(item.category, item.status.value) for item in requirements],
            "transaction": None if not transaction else {
                "type": transaction.transaction_type,
                "status": transaction.status,
                "approval": transaction.approval_status,
                "amount": str(transaction.committed_amount),
                "valuation": str(transaction.entry_valuation),
                "ownership": str(transaction.ownership_pct),
                "rationale": transaction.decision_rationale,
                "conditions": transaction.conditions_precedent,
                "evidence": transaction.evidence_file_ids,
            },
            "metrics": [(
                item.id, item.code, item.frequency, item.direction, str(item.target_value),
                str(item.watch_threshold), str(item.breach_threshold), item.source_description,
            ) for item in metrics],
            "observations": [(
                item.metric_id, item.period_end.isoformat(), str(item.value), item.status,
                item.source_file_id, item.note,
            ) for item in observations],
            "risks": [(
                item.id, item.severity, item.status, item.description, item.trigger_source, item.evidence_file_ids,
            ) for item in risks],
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
        integrity_ratio = sum(bool(item.checksum_sha256) for item in files) / max(source_count, 1)
        source_diversity = min(len({item.source_kind for item in files}) / 2, 1)
        trusted_ratio = sum(item.source_quality in {"official", "high", "verified"} for item in files) / max(source_count, 1)
        evidence_score = coverage * 50 + integrity_ratio * 15 + source_diversity * 10 + trusted_ratio * 10
        if project.investment_status == InvestmentStatus.in_progress:
            conditions = transaction.conditions_precedent if transaction else []
            unresolved_conditions = [
                item.get("label", "未命名条件") for item in conditions
                if item.get("status") not in {"satisfied", "waived"}
            ]
            gates_ready = bool(transaction and transaction.approval_status == "approved" and all(
                condition.get("status") in {"satisfied", "waived"}
                for condition in conditions
            ))
            recommendation = "hold_execution" if high_risks or not gates_ready else "proceed_with_controls"
            stage_score = 0
            if transaction:
                stage_score += 5
                stage_score += 5 if transaction.evidence_file_ids else 0
                stage_score += 5 if gates_ready else 0
        elif project.investment_status == InvestmentStatus.post_investment:
            recommendation = "escalate" if high_risks else "enhanced_monitoring" if watch_risks else "monitor"
            stage_score = min(len(metrics), 2) * 4 + (4 if observations else 0) + (
                3 if observations and all(item.source_file_id for item in observations[:3]) else 0
            )
        else:
            recommendation = "proceed_to_diligence" if coverage >= 0.75 and source_count >= 2 else "insufficient_evidence"
            stage_score = min(source_count, 3) * 5
        quality = min(100, round(evidence_score + stage_score, 2))
        confidence = "high" if quality >= 80 else "medium" if quality >= 55 else "low"
        evidence_markers = "".join(f"[E{index}]" for index, _ in enumerate(files[:5], start=1))
        fact_citation = evidence_markers or "（当前无可引用资料）"
        missing_requirements = [item.label for item in requirements if item.status != EvidenceStatus.covered]
        missing_text = "、".join(missing_requirements[:3]) or "无重大资料缺口"
        if project.investment_status == InvestmentStatus.in_progress:
            conclusion = "暂停交易执行" if recommendation == "hold_execution" else "仅在控制条件持续满足时推进交割"
            inference = (
                f"当前有 {len(unresolved_conditions)} 项未完成交割条件"
                if unresolved_conditions else "当前台账未发现未完成交割条件，但仍需在付款前复核证据有效性"
            )
            verification = "逐项复核投委批准、签署文件、收款账户、前置条件证据及正式豁免授权"
            gate = "投委批准有效、全部前置条件满足或正式豁免、签署与付款证据归档后方可交割"
            unknown = "实际资金路径、最终受益账户和未归档条件的法律效力"
            stage_heading = "投中执行"
        elif project.investment_status == InvestmentStatus.post_investment:
            conclusion = {
                "escalate": "升级投委处理并暂停依赖乐观假设的后续动作",
                "enhanced_monitoring": "维持增强监控",
                "monitor": "在既定阈值下持续监控",
            }[recommendation]
            risk_names = "、".join(item.title for item in risks[:3]) or "未发现开放风险事件"
            inference = f"当前风险信号为：{risk_names}；单期恢复不能自动证明风险已经消除"
            verification = "按指标口径复核原始凭证、连续周期趋势、预算偏差和风险整改证据"
            gate = "高风险或关键 KPI 越界提交投委；仅在连续周期达标且整改证据核验后降级"
            unknown = "缺失周期的经营表现、现金预测兑现率及未核验风险的最终影响"
            stage_heading = "投后监控"
        else:
            conclusion = "仅在资料条件满足后进入下一轮尽调" if recommendation == "proceed_to_diligence" else "证据不足，暂不形成投资判断"
            inference = f"当前主要证据缺口为：{missing_text}；覆盖度不足时不能外推估值或投资回报"
            verification = "补齐关键资料并对财务、客户、法律、市场与估值口径执行独立交叉核验"
            gate = "关键研究维度达到覆盖标准、重大矛盾完成调节、估值与下行情景经投委复核后再决策"
            unknown = "合理估值、增长可持续性、退出路径与风险调整后回报"
            stage_heading = "投前结论"
        thesis = "\n".join((
            f"{stage_heading}：{conclusion}（有条件）。",
            f"已核验事实：{source_count} 份资料通过意见证据准入 {fact_citation}；剔除 {excluded_public_count} 份关联性不足的公开资料；{covered}/{len(requirements)} 个研究维度达到覆盖标准；记录 {len(observations)} 个周期观测；存在 {high_risks} 个高风险和 {watch_risks} 个关注事件。",
            f"分析师推断：{inference}。",
            f"核验动作：{verification}；优先补充 {missing_text}。",
            f"投委门槛：{gate}。",
            f"无法判断：基于当前证据仍无法判断{unknown}。",
        ))
        previous = latest.recommendation if latest else "无历史版本"
        file_delta = source_count - (latest.source_count if latest else 0)
        recommendation_change = (
            f"建议由“{previous}”更新为“{recommendation}”"
            if previous != recommendation else f"建议维持“{recommendation}”"
        )
        change_summary = f"证据集发生变化（资料净增加 {file_delta} 份）；{recommendation_change}。"
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
    def _opinion_file_is_admissible(
        project: Project, file: ProjectFile, source: ResearchSource | None
    ) -> bool:
        if file.source_kind != "public_research":
            return True
        if not source or source.status != ResearchSourceStatus.ingested or not file.parsed_text:
            return False
        from app.services.research_service import ResearchService
        if source.evidence_category == "market":
            normalized = ResearchService._normalize_relevance_text(file.parsed_text)
            aliases = ResearchService._company_aliases(project.company_name)
            if max((normalized.count(alias) for alias in aliases), default=0) < 2:
                return False
        return ResearchService._content_is_relevant(project, source.evidence_category, file.parsed_text)

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
