"""initial schema

Bootstrap the base business tables that later migrations extend
(companies, users, optimization_jobs, vehicle_routes, locations,
matrix_cache). This is the migration-history equivalent of the old
database/schema-legacy.sql bootstrap: it must run before any migration
that adds foreign keys to companies/users.

Revision ID: 2f4a6c8e0b1d
Revises:
Create Date: 2026-08-18 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2f4a6c8e0b1d"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    op.create_table(
        "companies",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("plan", sa.String(50), nullable=False, server_default=sa.text("'free'")),
        sa.Column("stripe_customer_id", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default=sa.text("'member'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_users_email", "users", ["email"])

    op.create_table(
        "optimization_jobs",
        sa.Column("job_id", sa.UUID(), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("n_locations", sa.Integer(), nullable=False),
        sa.Column("n_vehicles", sa.Integer(), nullable=False),
        sa.Column("routing_backend", sa.String(20), nullable=False, server_default=sa.text("'haversine'")),
        sa.Column("solver_time_s", sa.Float()),
        sa.Column("total_distance_km", sa.Float()),
        sa.Column("total_time_min", sa.Float()),
        sa.Column("assigned_count", sa.Integer()),
        sa.Column("unassigned_count", sa.Integer()),
        sa.Column("request_json", JSONB()),
        sa.Column("response_json", JSONB()),
    )
    op.create_index("idx_jobs_created", "optimization_jobs", ["created_at"])
    op.create_index("idx_jobs_status", "optimization_jobs", ["status"])

    op.create_table(
        "vehicle_routes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.UUID(), sa.ForeignKey("optimization_jobs.job_id", ondelete="CASCADE"), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), nullable=False),
        sa.Column("route_json", JSONB(), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False),
        sa.Column("time_minutes", sa.Float(), nullable=False),
        sa.Column("packages", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_routes_job", "vehicle_routes", ["job_id"])

    op.create_table(
        "locations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.UUID(), sa.ForeignKey("optimization_jobs.job_id", ondelete="CASCADE"), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("demand", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("label", sa.String(200)),
        sa.Column("is_depot", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("assigned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("vehicle_id", sa.Integer()),
    )
    op.create_index("idx_locations_job", "locations", ["job_id"])
    op.create_index("idx_locations_assigned", "locations", ["job_id", "assigned"])

    op.create_table(
        "matrix_cache",
        sa.Column("cache_key", sa.String(64), primary_key=True),
        sa.Column("backend", sa.String(20), nullable=False),
        sa.Column("n_locations", sa.Integer(), nullable=False),
        sa.Column("distance_km", sa.LargeBinary(), nullable=False),
        sa.Column("duration_s", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now() + interval '24 hours'"),
        ),
    )
    op.create_index("idx_matrix_expires", "matrix_cache", ["expires_at"])


def downgrade() -> None:
    op.drop_index("idx_matrix_expires", table_name="matrix_cache")
    op.drop_table("matrix_cache")
    op.drop_index("idx_locations_assigned", table_name="locations")
    op.drop_index("idx_locations_job", table_name="locations")
    op.drop_table("locations")
    op.drop_index("idx_routes_job", table_name="vehicle_routes")
    op.drop_table("vehicle_routes")
    op.drop_index("idx_jobs_status", table_name="optimization_jobs")
    op.drop_index("idx_jobs_created", table_name="optimization_jobs")
    op.drop_table("optimization_jobs")
    op.drop_index("idx_users_email", table_name="users")
    op.drop_table("users")
    op.drop_table("companies")
