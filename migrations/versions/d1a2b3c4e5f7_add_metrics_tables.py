"""add metrics tables

Revision ID: d1a2b3c4e5f7
Revises: c0ffee123456
Create Date: 2025-10-30 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d1a2b3c4e5f7"
down_revision = "c0ffee123456"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_metrics",
        sa.Column("date", sa.String(), primary_key=True, nullable=False),
        sa.Column("total_sats", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("per_model_spend", sa.String(), nullable=False, server_default="{}"),
        sa.Column("per_model_requests", sa.String(), nullable=False, server_default="{}"),
        sa.Column("published_to_nostr", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
    )

    op.create_table(
        "request_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False, autoincrement=True),
        sa.Column("timestamp", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("sats_spent", sa.Integer(), nullable=False),
        sa.Column("api_key_hash", sa.String(), nullable=False),
    )

    op.create_index("ix_request_metrics_timestamp", "request_metrics", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_request_metrics_timestamp", table_name="request_metrics")
    op.drop_table("request_metrics")
    op.drop_table("daily_metrics")
