"""store the client-declared checksum for upload integrity validation"""

from alembic import op
import sqlalchemy as sa


revision = "20260710_0004"
down_revision = "20260710_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("project_files", sa.Column("expected_checksum_sha256", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("project_files", "expected_checksum_sha256")
