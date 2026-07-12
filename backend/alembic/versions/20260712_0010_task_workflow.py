"""add executable diligence task workflow"""

from alembic import op
import sqlalchemy as sa

revision = "20260712_0010"
down_revision = "20260711_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("project_tasks", sa.Column("status", sa.String(length=20), nullable=False, server_default="todo"))
    op.add_column("project_tasks", sa.Column("description", sa.Text(), nullable=False, server_default=""))
    op.add_column("project_tasks", sa.Column("assignee", sa.String(length=120), nullable=False, server_default=""))
    op.add_column("project_tasks", sa.Column("due_date", sa.DateTime(timezone=True), nullable=True))
    op.add_column("project_tasks", sa.Column("result", sa.Text(), nullable=False, server_default=""))
    op.add_column("project_tasks", sa.Column("related_requirement_id", sa.String(length=36), nullable=True))
    op.add_column("project_tasks", sa.Column("evidence_file_ids", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("project_tasks", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_project_tasks_related_requirement_id", "project_tasks", ["related_requirement_id"])
    op.create_foreign_key(
        "fk_project_tasks_related_requirement_id",
        "project_tasks",
        "evidence_requirements",
        ["related_requirement_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute("UPDATE project_tasks SET status = 'completed', completed_at = updated_at WHERE done = true")


def downgrade() -> None:
    op.drop_constraint("fk_project_tasks_related_requirement_id", "project_tasks", type_="foreignkey")
    op.drop_index("ix_project_tasks_related_requirement_id", table_name="project_tasks")
    for column in (
        "completed_at", "evidence_file_ids", "related_requirement_id", "result",
        "due_date", "assignee", "description", "status",
    ):
        op.drop_column("project_tasks", column)
