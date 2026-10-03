from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
    desired_job: Mapped[str] = mapped_column(String(200))
    major_experience: Mapped[str | None] = mapped_column(Text, nullable=True)
    owned_certifications: Mapped[list[str]] = mapped_column(JSON, default=list)
    target_acquisition_period: Mapped[str] = mapped_column(String(100))
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

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
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    session: Mapped[CoachingSession] = relationship(back_populates="schedules")
    recommendation: Mapped[CertificationRecommendation | None] = relationship(back_populates="schedules")
    certification: Mapped[Certification] = relationship(back_populates="schedules")

