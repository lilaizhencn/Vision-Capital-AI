"""add automatic project research scheduling state"""

from alembic import op
import sqlalchemy as sa

revision = "20260711_0009"
down_revision = "20260711_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("research_auto_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("projects", sa.Column("research_status", sa.String(length=20), nullable=False, server_default="idle"))
    op.add_column("projects", sa.Column("last_research_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("projects", sa.Column("next_research_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("projects", sa.Column("research_last_error", sa.Text(), nullable=True))
    op.create_index("ix_projects_next_research_at", "projects", ["next_research_at"])
    op.execute(
        "UPDATE projects SET next_research_at = CURRENT_TIMESTAMP "
        "WHERE research_auto_enabled = true AND next_research_at IS NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_projects_next_research_at", table_name="projects")
    op.drop_column("projects", "research_last_error")
    op.drop_column("projects", "next_research_at")
    op.drop_column("projects", "last_research_at")
    op.drop_column("projects", "research_status")
    op.drop_column("projects", "research_auto_enabled")
