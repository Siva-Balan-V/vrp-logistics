"""Add previous_job_id to optimization_jobs for ride-along replan tracking

Revision ID: d4e5f6a7b8c9
Revises: 486aea95548a
Create Date: 2026-09-06 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "486aea95548a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "optimization_jobs",
        sa.Column(
            "previous_job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("optimization_jobs.job_id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("idx_jobs_previous", "optimization_jobs", ["previous_job_id"])


def downgrade() -> None:
    op.drop_index("idx_jobs_previous", table_name="optimization_jobs")
    op.drop_column("optimization_jobs", "previous_job_id")
