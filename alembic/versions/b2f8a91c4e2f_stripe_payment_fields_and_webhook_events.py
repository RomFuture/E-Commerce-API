"""stripe payment fields and webhook idempotency table

Revision ID: b2f8a91c4e2f
Revises: 3e4cdc71234d
Create Date: 2026-04-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2f8a91c4e2f"
down_revision: str | Sequence[str] | None = "3e4cdc71234d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column(
            "provider",
            sa.String(length=32),
            server_default=sa.text("'stripe'"),
            nullable=False,
        ),
    )
    op.add_column(
        "payments",
        sa.Column("stripe_checkout_session_id", sa.String(length=255), nullable=True),
    )
    op.create_unique_constraint(
        "uq_payments_stripe_checkout_session_id",
        "payments",
        ["stripe_checkout_session_id"],
    )

    op.create_table(
        "processed_webhook_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )


def downgrade() -> None:
    op.drop_table("processed_webhook_events")
    op.drop_constraint("uq_payments_stripe_checkout_session_id", "payments", type_="unique")
    op.drop_column("payments", "stripe_checkout_session_id")
    op.drop_column("payments", "provider")
