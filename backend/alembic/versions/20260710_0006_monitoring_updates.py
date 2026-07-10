"""add post-investment monitoring updates"""

from alembic import op
import sqlalchemy as sa

revision = "20260710_0006"
down_revision = "20260710_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "monitoring_updates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_name", sa.String(length=120), nullable=False),
        sa.Column("metric_value", sa.String(length=120), nullable=False),
        sa.Column("metric_unit", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("risk_level", sa.String(length=20), nullable=False, server_default="normal"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_monitoring_updates_project_id", "monitoring_updates", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_monitoring_updates_project_id", table_name="monitoring_updates")
    op.drop_table("monitoring_updates")
