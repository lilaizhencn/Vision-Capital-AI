"""add professional investment lifecycle controls"""

from alembic import op
import sqlalchemy as sa

revision = "20260712_0011"
down_revision = "20260712_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transaction_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transaction_type", sa.String(32), nullable=False, server_default="equity"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="CNY"),
        sa.Column("committed_amount", sa.Numeric(20, 2)),
        sa.Column("entry_valuation", sa.Numeric(20, 2)),
        sa.Column("ownership_pct", sa.Numeric(9, 4)),
        sa.Column("status", sa.String(24), nullable=False, server_default="drafting"),
        sa.Column("approval_status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("decision_rationale", sa.Text(), nullable=False, server_default=""),
        sa.Column("conditions_precedent", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("evidence_file_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", name="uq_transaction_execution_project"),
    )
    op.create_index("ix_transaction_executions_project_id", "transaction_executions", ["project_id"])
    op.create_table(
        "monitoring_metrics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("unit", sa.String(40), nullable=False, server_default=""),
        sa.Column("frequency", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("direction", sa.String(20), nullable=False, server_default="higher_better"),
        sa.Column("baseline_value", sa.Numeric(24, 6)),
        sa.Column("target_value", sa.Numeric(24, 6)),
        sa.Column("watch_threshold", sa.Numeric(24, 6)),
        sa.Column("breach_threshold", sa.Numeric(24, 6)),
        sa.Column("owner", sa.String(120), nullable=False, server_default=""),
        sa.Column("source_description", sa.String(500), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "code", name="uq_monitoring_metric_project_code"),
    )
    op.create_index("ix_monitoring_metrics_project_id", "monitoring_metrics", ["project_id"])
    op.create_table(
        "monitoring_observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_id", sa.String(36), sa.ForeignKey("monitoring_metrics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(24, 6), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("variance_from_target", sa.Numeric(24, 6)),
        sa.Column("source_file_id", sa.String(36), sa.ForeignKey("project_files.id", ondelete="SET NULL")),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("metric_id", "period_end", name="uq_monitoring_observation_period"),
    )
    op.create_index("ix_monitoring_observations_project_id", "monitoring_observations", ["project_id"])
    op.create_index("ix_monitoring_observations_metric_id", "monitoring_observations", ["metric_id"])
    op.create_table(
        "risk_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("observation_id", sa.String(36), sa.ForeignKey("monitoring_observations.id", ondelete="SET NULL"), unique=True),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="watch"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("trigger_source", sa.String(500), nullable=False, server_default="manual"),
        sa.Column("evidence_file_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_risk_events_project_id", "risk_events", ["project_id"])
    op.create_table(
        "investment_opinion_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("recommendation", sa.String(40), nullable=False),
        sa.Column("confidence", sa.String(20), nullable=False),
        sa.Column("quality_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("thesis", sa.Text(), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=False),
        sa.Column("evidence_hash", sa.String(64), nullable=False),
        sa.Column("evidence_file_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "version", name="uq_investment_opinion_project_version"),
    )
    op.create_index("ix_investment_opinion_versions_project_id", "investment_opinion_versions", ["project_id"])
    op.create_index("ix_investment_opinion_versions_evidence_hash", "investment_opinion_versions", ["evidence_hash"])
    op.create_table(
        "data_source_subscriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("cadence_hours", sa.Integer(), nullable=False, server_default="168"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "url", name="uq_data_source_subscription_project_url"),
    )
    op.create_index("ix_data_source_subscriptions_project_id", "data_source_subscriptions", ["project_id"])
    op.create_index("ix_data_source_subscriptions_next_run_at", "data_source_subscriptions", ["next_run_at"])


def downgrade() -> None:
    for table in (
        "data_source_subscriptions", "investment_opinion_versions", "risk_events",
        "monitoring_observations", "monitoring_metrics", "transaction_executions",
    ):
        op.drop_table(table)
