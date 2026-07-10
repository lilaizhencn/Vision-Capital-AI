"""add resilient batch upload and parse progress tracking"""

from alembic import op
import sqlalchemy as sa

revision = "20260710_0002"
down_revision = "20260710_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    batch_status = sa.Enum("uploading", "queued", "processing", "completed", "failed", name="batch_status", create_type=False)
    parse_stage = sa.Enum("upload", "validate", "ocr", "table_extract", "llm_extract", "persist", "completed", name="parse_stage", create_type=False)
    batch_status.create(bind, checkfirst=True)
    parse_stage.create(bind, checkfirst=True)
    op.create_table(
        "document_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("total_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", batch_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_document_batches_project_id", "document_batches", ["project_id"])
    op.add_column("project_files", sa.Column("batch_id", sa.String(36), sa.ForeignKey("document_batches.id", ondelete="SET NULL"), nullable=True))
    op.add_column("project_files", sa.Column("parse_stage", parse_stage, nullable=False, server_default="upload"))
    op.add_column("project_files", sa.Column("progress", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("project_files", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("project_files", sa.Column("checksum_sha256", sa.String(64), nullable=True))
    op.add_column("project_files", sa.Column("multipart_upload_id", sa.String(255), nullable=True))
    op.create_index("ix_project_files_batch_id", "project_files", ["batch_id"])


def downgrade() -> None:
    op.drop_index("ix_project_files_batch_id", table_name="project_files")
    for name in ("multipart_upload_id", "checksum_sha256", "retry_count", "progress", "parse_stage", "batch_id"):
        op.drop_column("project_files", name)
    op.drop_index("ix_document_batches_project_id", table_name="document_batches")
    op.drop_table("document_batches")
    sa.Enum(name="parse_stage").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="batch_status").drop(op.get_bind(), checkfirst=True)
