"""persist structured extraction results and parse dead letters"""

from alembic import op
import sqlalchemy as sa


revision = "20260710_0003"
down_revision = "20260710_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("project_files", sa.Column("extracted_data", sa.JSON(), nullable=True))
    op.create_table(
        "parse_dead_letters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("project_files.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_parse_dead_letters_file_id", "parse_dead_letters", ["file_id"])


def downgrade() -> None:
    op.drop_index("ix_parse_dead_letters_file_id", table_name="parse_dead_letters")
    op.drop_table("parse_dead_letters")
    op.drop_column("project_files", "extracted_data")
