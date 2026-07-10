"""add persistent project diligence tasks"""

from alembic import op
import sqlalchemy as sa

revision = "20260710_0007"
down_revision = "20260710_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_tasks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_project_tasks_project_id", "project_tasks", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_tasks_project_id", table_name="project_tasks")
    op.drop_table("project_tasks")
