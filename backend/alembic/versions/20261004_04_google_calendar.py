"""Add private-session Google Calendar integration.

Revision ID: 20261004_04
Revises: 20261004_03
Create Date: 2026-10-04
"""

import sqlalchemy as sa

from alembic import op

revision = "20261004_04"
down_revision = "20261004_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "certification_schedules",
        sa.Column("source_verified", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.alter_column("certification_schedules", "source_verified", server_default=None)

    op.create_table(
        "google_oauth_states",
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["coaching_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("state_hash"),
    )
    op.create_index("ix_google_oauth_states_session_id", "google_oauth_states", ["session_id"])
    op.create_index("ix_google_oauth_states_expires_at", "google_oauth_states", ["expires_at"])

    op.create_table(
        "google_calendar_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("calendar_id", sa.String(length=500), nullable=False),
        sa.Column("calendar_name", sa.String(length=200), nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=False),
        sa.Column("granted_scopes", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="connected"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["coaching_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )

    op.create_table(
        "calendar_event_syncs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("schedule_id", sa.Integer(), nullable=False),
        sa.Column("google_calendar_id", sa.String(length=500), nullable=False),
        sa.Column("google_event_id", sa.String(length=128), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["coaching_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["schedule_id"], ["certification_schedules.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "schedule_id"),
    )
    op.create_index("ix_calendar_event_syncs_session_id", "calendar_event_syncs", ["session_id"])
    op.create_index("ix_calendar_event_syncs_schedule_id", "calendar_event_syncs", ["schedule_id"])


def downgrade() -> None:
    op.drop_index("ix_calendar_event_syncs_schedule_id", table_name="calendar_event_syncs")
    op.drop_index("ix_calendar_event_syncs_session_id", table_name="calendar_event_syncs")
    op.drop_table("calendar_event_syncs")
    op.drop_table("google_calendar_connections")
    op.drop_index("ix_google_oauth_states_expires_at", table_name="google_oauth_states")
    op.drop_index("ix_google_oauth_states_session_id", table_name="google_oauth_states")
    op.drop_table("google_oauth_states")
    op.drop_column("certification_schedules", "source_verified")
