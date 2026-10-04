"""Add dashboard profile fields and make legacy session input optional.

Revision ID: 20261004_03
Revises: 20261004_02
Create Date: 2026-10-04
"""

import sqlalchemy as sa

from alembic import op

revision = "20261004_03"
down_revision = "20261004_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Earlier demo runs may have persisted generated dates from the mock adapter.
    op.execute(
        "DELETE FROM certification_schedules "
        "WHERE source_name = 'Mock Official Schedule Adapter'"
    )

    op.add_column("coaching_sessions", sa.Column("interest_area", sa.String(length=200), nullable=True))
    op.add_column(
        "coaching_sessions", sa.Column("weekly_study_hours", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "coaching_sessions", sa.Column("learning_style", sa.String(length=100), nullable=True)
    )
    op.add_column("coaching_sessions", sa.Column("monthly_budget", sa.String(length=100), nullable=True))

    op.alter_column(
        "coaching_sessions",
        "desired_job",
        existing_type=sa.String(length=200),
        nullable=True,
    )
    op.alter_column(
        "coaching_sessions",
        "owned_certifications",
        existing_type=sa.JSON(),
        nullable=True,
    )
    op.alter_column(
        "coaching_sessions",
        "target_acquisition_period",
        existing_type=sa.String(length=100),
        nullable=True,
    )


def downgrade() -> None:
    op.drop_column("coaching_sessions", "monthly_budget")
    op.drop_column("coaching_sessions", "learning_style")
    op.drop_column("coaching_sessions", "weekly_study_hours")
    op.drop_column("coaching_sessions", "interest_area")
    # Keep legacy columns nullable on downgrade rather than inventing values for new sessions.
    # Removed mock schedule rows are intentionally not restored.
