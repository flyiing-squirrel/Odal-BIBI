"""Create the initial coaching schema and seed its certification catalog.

Revision ID: 20261004_01
Revises:
Create Date: 2026-10-04
"""

import sqlalchemy as sa

from alembic import op

revision = "20261004_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "certifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("issuer", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("official_url", sa.String(length=500), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_certifications_code", "certifications", ["code"], unique=True)

    op.create_table(
        "coaching_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("desired_job", sa.String(length=200), nullable=False),
        sa.Column("major_experience", sa.Text(), nullable=True),
        sa.Column("owned_certifications", sa.JSON(), nullable=False),
        sa.Column("target_acquisition_period", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "certification_recommendations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("certification_id", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("match_score", sa.Float(), nullable=False),
        sa.Column("priority", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("study_plan_hint", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["certification_id"], ["certifications.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["coaching_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_certification_recommendations_certification_id",
        "certification_recommendations",
        ["certification_id"],
    )
    op.create_index(
        "ix_certification_recommendations_session_id",
        "certification_recommendations",
        ["session_id"],
    )

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["coaching_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_messages_session_id", "conversation_messages", ["session_id"]
    )

    op.create_table(
        "certification_schedules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.Integer(), nullable=True),
        sa.Column("certification_id", sa.Integer(), nullable=False),
        sa.Column("exam_name", sa.String(length=200), nullable=False),
        sa.Column("registration_start", sa.Date(), nullable=True),
        sa.Column("registration_end", sa.Date(), nullable=True),
        sa.Column("exam_date", sa.Date(), nullable=False),
        sa.Column("result_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("source_name", sa.String(length=200), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["certification_id"], ["certifications.id"]),
        sa.ForeignKeyConstraint(["recommendation_id"], ["certification_recommendations.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["coaching_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_certification_schedules_certification_id",
        "certification_schedules",
        ["certification_id"],
    )
    op.create_index(
        "ix_certification_schedules_recommendation_id",
        "certification_schedules",
        ["recommendation_id"],
    )
    op.create_index(
        "ix_certification_schedules_session_id", "certification_schedules", ["session_id"]
    )

    catalog = sa.table(
        "certifications",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("issuer", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("official_url", sa.String()),
    )
    op.bulk_insert(
        catalog,
        [
            {
                "code": "INFO_PROCESSOR_ENGINEER",
                "name": "정보처리기사",
                "issuer": "한국산업인력공단",
                "description": "소프트웨어 설계·개발·데이터베이스·프로그래밍 역량을 종합적으로 검증하는 국가기술자격입니다.",
                "official_url": "https://www.q-net.or.kr/crf005.do?id=crf00503&jmCd=1320",
            },
            {
                "code": "SQLD",
                "name": "SQLD",
                "issuer": "한국데이터산업진흥원",
                "description": "데이터 모델링과 SQL 기본·활용 역량을 검증하는 자격입니다.",
                "official_url": "https://www.dataq.or.kr/www/accept/schedule.do",
            },
            {
                "code": "ADSP",
                "name": "ADsP",
                "issuer": "한국데이터산업진흥원",
                "description": "데이터 이해, 분석 기획, 데이터 분석 기초 역량을 검증하는 자격입니다.",
                "official_url": "https://www.dataq.or.kr/www/accept/schedule.do",
            },
            {
                "code": "BIGDATA_ENGINEER",
                "name": "빅데이터분석기사",
                "issuer": "한국산업인력공단",
                "description": "빅데이터 분석 기획부터 수집·처리·분석·시각화까지의 실무 역량을 검증합니다.",
                "official_url": "https://www.q-net.or.kr/crf005.do?id=crf00503&jmCd=1321",
            },
            {
                "code": "AWS_SAA",
                "name": "AWS Certified Solutions Architect - Associate",
                "issuer": "Amazon Web Services",
                "description": "AWS 기반의 보안성·복원력·고성능·비용 효율적 아키텍처 설계 역량을 검증합니다.",
                "official_url": "https://aws.amazon.com/certification/certified-solutions-architect-associate/",
            },
            {
                "code": "SOCIETY_ANALYST_2",
                "name": "사회조사분석사 2급",
                "issuer": "한국산업인력공단",
                "description": "사회조사 설계, 자료 수집, 통계 분석 역량을 검증하는 국가기술자격입니다.",
                "official_url": "https://www.q-net.or.kr/crf005.do?id=crf00503&jmCd=1740",
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("certification_schedules")
    op.drop_table("conversation_messages")
    op.drop_table("certification_recommendations")
    op.drop_table("coaching_sessions")
    op.drop_table("certifications")
