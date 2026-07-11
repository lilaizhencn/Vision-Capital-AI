"""add public research provenance and evidence requirements"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260711_0008"
down_revision = "20260710_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    evidence_status = postgresql.ENUM("missing", "partial", "covered", name="evidence_status", create_type=False)
    source_status = postgresql.ENUM("discovered", "ingested", "review_required", "failed", name="research_source_status", create_type=False)
    evidence_status.create(op.get_bind(), checkfirst=True)
    source_status.create(op.get_bind(), checkfirst=True)
    op.add_column("project_files", sa.Column("source_kind", sa.String(length=32), nullable=False, server_default="upload"))
    op.add_column("project_files", sa.Column("source_url", sa.String(length=2048), nullable=True))
    op.add_column("project_files", sa.Column("source_quality", sa.String(length=32), nullable=True))
    op.create_table(
        "evidence_requirements",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("status", evidence_status, nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("suggested_document", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", "category", name="uq_evidence_requirement_project_category"),
    )
    op.create_index("ix_evidence_requirements_project_id", "evidence_requirements", ["project_id"])
    op.create_table(
        "research_sources",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", sa.String(length=36), sa.ForeignKey("project_files.id", ondelete="SET NULL"), nullable=True),
        sa.Column("evidence_category", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("publisher", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("url_hash", sa.String(length=64), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=False, server_default=""),
        sa.Column("quality", sa.String(length=32), nullable=False, server_default="official"),
        sa.Column("status", source_status, nullable=False, server_default="discovered"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("project_id", "url_hash", name="uq_research_source_project_url"),
    )
    op.create_index("ix_research_sources_project_id", "research_sources", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_research_sources_project_id", table_name="research_sources")
    op.drop_table("research_sources")
    op.drop_index("ix_evidence_requirements_project_id", table_name="evidence_requirements")
    op.drop_table("evidence_requirements")
    op.drop_column("project_files", "source_quality")
    op.drop_column("project_files", "source_url")
    op.drop_column("project_files", "source_kind")
    sa.Enum(name="research_source_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="evidence_status").drop(op.get_bind(), checkfirst=True)
