"""add stage artifacts, virus scan state, and stage idempotency records"""

from alembic import op
import sqlalchemy as sa


revision = "20260710_0005"
down_revision = "20260710_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("project_files", sa.Column("parsed_text", sa.Text(), nullable=True))
    op.add_column("project_files", sa.Column("table_text", sa.Text(), nullable=True))
    op.add_column("project_files", sa.Column("virus_scan_status", sa.String(length=32), nullable=False, server_default="pending"))
    op.add_column("project_files", sa.Column("virus_scan_result", sa.Text(), nullable=True))
    op.create_table(
        "parse_stage_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("project_files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="running"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_parse_stage_runs_file_id", "parse_stage_runs", ["file_id"])


def downgrade() -> None:
    op.drop_index("ix_parse_stage_runs_file_id", table_name="parse_stage_runs")
    op.drop_table("parse_stage_runs")
    op.drop_column("project_files", "virus_scan_result")
    op.drop_column("project_files", "virus_scan_status")
    op.drop_column("project_files", "table_text")
    op.drop_column("project_files", "parsed_text")
