from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class Certification(Base):
    __tablename__ = "certifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    issuer: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    official_url: Mapped[str] = mapped_column(String(500))

    recommendations: Mapped[list["CertificationRecommendation"]] = relationship(
        back_populates="certification"
    )
    schedules: Mapped[list["CertificationSchedule"]] = relationship(back_populates="certification")


class CoachingSession(Base):
    __tablename__ = "coaching_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    desired_job: Mapped[str | None] = mapped_column(String(200), nullable=True)
    major_experience: Mapped[str | None] = mapped_column(Text, nullable=True)
    owned_certifications: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    target_acquisition_period: Mapped[str | None] = mapped_column(String(100), nullable=True)
    session_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    interest_area: Mapped[str | None] = mapped_column(String(200), nullable=True)
    weekly_study_hours: Mapped[str | None] = mapped_column(String(100), nullable=True)
    learning_style: Mapped[str | None] = mapped_column(String(100), nullable=True)
    monthly_budget: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    recommendations: Mapped[list["CertificationRecommendation"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="CertificationRecommendation.rank",
    )
    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ConversationMessage.id"
    )
    schedules: Mapped[list["CertificationSchedule"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="CertificationSchedule.exam_date",
    )
    google_oauth_states: Mapped[list["GoogleOAuthState"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    google_calendar_connection: Mapped["GoogleCalendarConnection | None"] = relationship(
        back_populates="session", cascade="all, delete-orphan", uselist=False
    )


class CertificationRecommendation(Base):
    __tablename__ = "certification_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("coaching_sessions.id"), index=True)
    certification_id: Mapped[int] = mapped_column(ForeignKey("certifications.id"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    match_score: Mapped[float] = mapped_column(Float)
    priority: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text)
    study_plan_hint: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    session: Mapped[CoachingSession] = relationship(back_populates="recommendations")
    certification: Mapped[Certification] = relationship(back_populates="recommendations")
    schedules: Mapped[list["CertificationSchedule"]] = relationship(back_populates="recommendation")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("coaching_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    # assistant 답변의 근거 출처 [{title, url}]. 답변 본문의 [n]과 순서가 같다.
    sources: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    session: Mapped[CoachingSession] = relationship(back_populates="messages")


class CertificationSchedule(Base):
    __tablename__ = "certification_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("coaching_sessions.id"), index=True)
    recommendation_id: Mapped[int | None] = mapped_column(
        ForeignKey("certification_recommendations.id"), nullable=True, index=True
    )
    certification_id: Mapped[int] = mapped_column(ForeignKey("certifications.id"), index=True)
    exam_name: Mapped[str] = mapped_column(String(200))
    registration_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    registration_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    exam_date: Mapped[date] = mapped_column(Date)
    result_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30))
    source_name: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str] = mapped_column(String(500))
    source_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    session: Mapped[CoachingSession] = relationship(back_populates="schedules")
    recommendation: Mapped[CertificationRecommendation | None] = relationship(back_populates="schedules")
    certification: Mapped[Certification] = relationship(back_populates="schedules")
    calendar_event_sync: Mapped["CalendarEventSync | None"] = relationship(
        back_populates="schedule", cascade="all, delete-orphan", uselist=False
    )


class GoogleOAuthState(Base):
    __tablename__ = "google_oauth_states"

    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("coaching_sessions.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    session: Mapped[CoachingSession] = relationship(back_populates="google_oauth_states")


class GoogleCalendarConnection(Base):
    __tablename__ = "google_calendar_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("coaching_sessions.id", ondelete="CASCADE"), unique=True
    )
    calendar_id: Mapped[str] = mapped_column(String(500))
    calendar_name: Mapped[str] = mapped_column(String(200))
    encrypted_refresh_token: Mapped[str] = mapped_column(Text)
    granted_scopes: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="connected")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    session: Mapped[CoachingSession] = relationship(back_populates="google_calendar_connection")


class CalendarEventSync(Base):
    __tablename__ = "calendar_event_syncs"
    __table_args__ = (UniqueConstraint("session_id", "schedule_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("coaching_sessions.id", ondelete="CASCADE"), index=True
    )
    schedule_id: Mapped[int] = mapped_column(
        ForeignKey("certification_schedules.id", ondelete="CASCADE"), index=True
    )
    google_calendar_id: Mapped[str] = mapped_column(String(500))
    google_event_id: Mapped[str] = mapped_column(String(128))
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    schedule: Mapped[CertificationSchedule] = relationship(back_populates="calendar_event_sync")


class RequestRateLimit(Base):
    __tablename__ = "request_rate_limits"

    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    request_count: Mapped[int] = mapped_column(Integer)

