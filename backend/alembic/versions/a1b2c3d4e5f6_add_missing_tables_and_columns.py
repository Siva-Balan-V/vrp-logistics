"""add missing tables and columns

Revision ID: a1b2c3d4e5f6
Revises: 50e7a5c47b13
Create Date: 2026-08-18 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "50e7a5c47b13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create drivers table first (needed for FK references)
    op.create_table(
        "drivers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="offline"),
        sa.Column("current_lat", sa.Float, nullable=True),
        sa.Column("current_lon", sa.Float, nullable=True),
        sa.Column("last_ping_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_drivers_company", "drivers", ["company_id"])

    # 2. Add company_id to optimization_jobs
    op.add_column(
        "optimization_jobs",
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=True),
    )
    op.create_index("idx_jobs_company", "optimization_jobs", ["company_id"])

    # 3. Add driver_id to vehicle_routes (drivers table now exists)
    op.add_column(
        "vehicle_routes",
        sa.Column("driver_id", UUID(as_uuid=True), sa.ForeignKey("drivers.id"), nullable=True),
    )

    # 4. Create notification_config table
    op.create_table(
        "notification_config",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False, unique=True),
        sa.Column("sms_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("email_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("twilio_account_sid", sa.String(255)),
        sa.Column("twilio_auth_token", sa.String(255)),
        sa.Column("twilio_from_number", sa.String(20)),
        sa.Column("smtp_host", sa.String(255)),
        sa.Column("smtp_port", sa.Integer, server_default="587"),
        sa.Column("smtp_user", sa.String(255)),
        sa.Column("smtp_password", sa.String(255)),
        sa.Column("smtp_from_email", sa.String(255)),
        sa.Column("triggers", JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # 5. Create notification_log table
    op.create_table(
        "notification_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("driver_id", UUID(as_uuid=True), sa.ForeignKey("drivers.id"), nullable=True),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("recipient", sa.String(255), nullable=False),
        sa.Column("trigger", sa.String(50), nullable=False),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="sent"),
        sa.Column("error", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("notification_log")
    op.drop_table("notification_config")
    op.drop_column("vehicle_routes", "driver_id")
    op.drop_index("idx_jobs_company", table_name="optimization_jobs")
    op.drop_column("optimization_jobs", "company_id")
    op.drop_index("idx_drivers_company", table_name="drivers")
    op.drop_table("drivers")
