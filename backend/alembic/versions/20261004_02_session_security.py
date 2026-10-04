"""Add session capability hashes and shared request-limit counters.

Revision ID: 20261004_02
Revises: 20261004_01
Create Date: 2026-10-04
"""

import sqlalchemy as sa

from alembic import op

revision = "20261004_02"
down_revision = "20261004_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "coaching_sessions",
        sa.Column("session_token_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_coaching_sessions_session_token_hash",
        "coaching_sessions",
        ["session_token_hash"],
        unique=True,
    )
    op.create_table(
        "request_rate_limits",
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("key_hash"),
    )


def downgrade() -> None:
    op.drop_table("request_rate_limits")
    op.drop_index(
        "ix_coaching_sessions_session_token_hash",
        table_name="coaching_sessions",
    )
    op.drop_column("coaching_sessions", "session_token_hash")
