"""add_razorpay_columns_to_companies

Revision ID: 486aea95548a
Revises: a1b2c3d4e5f6
Create Date: 2026-08-22 20:03:20.426396

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "486aea95548a"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("razorpay_order_id", sa.String(length=255), nullable=True))
    op.add_column("companies", sa.Column("razorpay_payment_id", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "razorpay_payment_id")
    op.drop_column("companies", "razorpay_order_id")
