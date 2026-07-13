"""add per-user daily AI usage quota"""

from alembic import op
import sqlalchemy as sa


revision = "20260713_0012"
down_revision = "20260712_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("operation_key", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("operation_key", name="uq_ai_usage_event_operation_key"),
    )
    op.create_index("ix_ai_usage_events_user_id", "ai_usage_events", ["user_id"])
    op.create_index("ix_ai_usage_events_user_date", "ai_usage_events", ["user_id", "usage_date"])


def downgrade() -> None:
    op.drop_table("ai_usage_events")
