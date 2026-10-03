"""Add Google identity and dedicated-calendar sync storage."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20261003_0001"
down_revision = None
branch_labels = None
depends_on = None


def _create_legacy_tables() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("certifications"):
        op.create_table(
            "certifications",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(80), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("issuer", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("official_url", sa.String(500), nullable=False),
        )
    if not inspector.has_table("coaching_sessions"):
        op.create_table(
            "coaching_sessions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("desired_job", sa.String(200), nullable=False),
            sa.Column("major_experience", sa.Text(), nullable=True),
            sa.Column("owned_certifications", sa.JSON(), nullable=False),
            sa.Column("target_acquisition_period", sa.String(100), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    if not inspector.has_table("certification_recommendations"):
        op.create_table(
            "certification_recommendations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("session_id", sa.Integer(), sa.ForeignKey("coaching_sessions.id"), nullable=False),
            sa.Column("certification_id", sa.Integer(), sa.ForeignKey("certifications.id"), nullable=False),
            sa.Column("rank", sa.Integer(), nullable=False),
            sa.Column("match_score", sa.Float(), nullable=False),
            sa.Column("priority", sa.String(30), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("study_plan_hint", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    if not inspector.has_table("conversation_messages"):
        op.create_table(
            "conversation_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("session_id", sa.Integer(), sa.ForeignKey("coaching_sessions.id"), nullable=False),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    if not inspector.has_table("certification_schedules"):
        op.create_table(
            "certification_schedules",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("session_id", sa.Integer(), sa.ForeignKey("coaching_sessions.id"), nullable=False),
            sa.Column("recommendation_id", sa.Integer(), sa.ForeignKey("certification_recommendations.id"), nullable=True),
            sa.Column("certification_id", sa.Integer(), sa.ForeignKey("certifications.id"), nullable=False),
            sa.Column("exam_name", sa.String(200), nullable=False),
            sa.Column("registration_start", sa.Date(), nullable=True),
            sa.Column("registration_end", sa.Date(), nullable=True),
            sa.Column("exam_date", sa.Date(), nullable=False),
            sa.Column("result_date", sa.Date(), nullable=True),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("source_name", sa.String(200), nullable=False),
            sa.Column("source_url", sa.String(500), nullable=False),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        )
    for table_name, column_name in (
        ("certifications", "code"),
        ("certification_recommendations", "session_id"),
        ("certification_recommendations", "certification_id"),
        ("conversation_messages", "session_id"),
        ("certification_schedules", "session_id"),
        ("certification_schedules", "recommendation_id"),
        ("certification_schedules", "certification_id"),
    ):
        index_name = f"ix_{table_name}_{column_name}"
        indexes = {index["name"] for index in inspect(op.get_bind()).get_indexes(table_name)}
        if index_name not in indexes:
            op.create_index(
                index_name,
                table_name,
                [column_name],
                unique=table_name == "certifications",
            )


def upgrade() -> None:
    _create_legacy_tables()
    inspector = inspect(op.get_bind())
    if not inspector.has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("google_sub", sa.String(255), nullable=False),
            sa.Column("email", sa.String(320), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)

    inspector = inspect(op.get_bind())
    if "user_id" not in {column["name"] for column in inspector.get_columns("coaching_sessions")}:
        op.add_column(
            "coaching_sessions",
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        )
        op.create_index("ix_coaching_sessions_user_id", "coaching_sessions", ["user_id"])
    if "source_verified" not in {column["name"] for column in inspector.get_columns("certification_schedules")}:
        op.add_column(
            "certification_schedules",
            sa.Column("source_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    if not inspect(op.get_bind()).has_table("google_calendar_connections"):
        op.create_table(
            "google_calendar_connections",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("calendar_id", sa.String(500), nullable=True),
            sa.Column("calendar_summary", sa.String(200), nullable=False, server_default="Odal BIBI"),
            sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
            sa.Column("granted_scopes", sa.Text(), nullable=False, server_default=""),
            sa.Column("status", sa.String(40), nullable=False, server_default="setup_required"),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
    if not inspect(op.get_bind()).has_table("calendar_event_syncs"):
        op.create_table(
            "calendar_event_syncs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("schedule_id", sa.Integer(), sa.ForeignKey("certification_schedules.id", ondelete="CASCADE"), nullable=False),
            sa.Column("calendar_id", sa.String(500), nullable=False),
            sa.Column("google_event_id", sa.String(128), nullable=False),
            sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("user_id", "schedule_id", name="uq_calendar_sync_user_schedule"),
        )
        op.create_index("ix_calendar_event_syncs_user_id", "calendar_event_syncs", ["user_id"])
        op.create_index("ix_calendar_event_syncs_schedule_id", "calendar_event_syncs", ["schedule_id"])


def downgrade() -> None:
    op.drop_index("ix_calendar_event_syncs_schedule_id", table_name="calendar_event_syncs")
    op.drop_index("ix_calendar_event_syncs_user_id", table_name="calendar_event_syncs")
    op.drop_table("calendar_event_syncs")
    op.drop_table("google_calendar_connections")
    op.drop_index("ix_coaching_sessions_user_id", table_name="coaching_sessions")
    with op.batch_alter_table("certification_schedules") as batch_op:
        batch_op.drop_column("source_verified")
    with op.batch_alter_table("coaching_sessions") as batch_op:
        batch_op.drop_column("user_id")
    op.drop_index("ix_users_google_sub", table_name="users")
    op.drop_table("users")
