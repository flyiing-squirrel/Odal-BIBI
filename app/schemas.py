from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CoachInput(BaseModel):
    """The four inputs collected by the dashboard."""

    desired_job: str = Field(..., min_length=1, max_length=200, description="희망직무")
    major_experience: str | None = Field(default=None, max_length=3000, description="전공 관련 경험")
    owned_certifications: list[str] = Field(default_factory=list, description="보유 자격증")
    target_acquisition_period: str = Field(
        ..., min_length=1, max_length=100, description="목표 취득 시기"
    )


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    desired_job: str
    major_experience: str | None
    owned_certifications: list[str]
    target_acquisition_period: str
    created_at: datetime


class CertificationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    issuer: str
    description: str
    official_url: str


class RecommendationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rank: int
    match_score: float
    priority: str
    reason: str
    study_plan_hint: str
    certification: CertificationSummary


class RecommendationDetail(RecommendationSummary):
    schedules: list["ScheduleResponse"] = Field(default_factory=list)


class ConversationMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime


class ScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recommendation_id: int | None
    exam_name: str
    registration_start: date | None
    registration_end: date | None
    exam_date: date
    result_date: date | None
    status: str
    source_name: str
    source_url: str
    details: str | None
    fetched_at: datetime
    certification: CertificationSummary


class DashboardResponse(BaseModel):
    session: SessionResponse
    recommendations: list[RecommendationSummary]
    conversation: list[ConversationMessageResponse]
    schedules: list[ScheduleResponse]


class MessageListResponse(BaseModel):
    session_id: int
    items: list[ConversationMessageResponse]


class RecommendationListResponse(BaseModel):
    session_id: int
    items: list[RecommendationSummary]


class ScheduleListResponse(BaseModel):
    session_id: int
    items: list[ScheduleResponse]

