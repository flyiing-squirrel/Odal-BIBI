from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CoachInput(BaseModel):
    """Profile fields collected by the dashboard plus optional legacy fields."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    interest_area: str = Field(..., min_length=1, max_length=200, description="관심 분야")
    weekly_study_hours: str | None = Field(default=None, max_length=100, description="주간 학습 시간")
    learning_style: str | None = Field(default=None, max_length=100, description="선호 학습 방식")
    monthly_budget: str | None = Field(default=None, max_length=100, description="월 학습 예산")
    desired_job: str | None = Field(default=None, max_length=200, description="이전 버전 희망직무")
    major_experience: str | None = Field(default=None, max_length=3000, description="이전 버전 전공 경험")
    owned_certifications: list[str] | None = Field(default=None, description="이전 버전 보유 자격증")
    target_acquisition_period: str | None = Field(default=None, max_length=100, description="이전 버전 목표 시기")


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    interest_area: str | None = Field(default=None, min_length=1, max_length=200)
    weekly_study_hours: str | None = Field(default=None, max_length=100)
    learning_style: str | None = Field(default=None, max_length=100)
    monthly_budget: str | None = Field(default=None, max_length=100)


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    desired_job: str | None
    major_experience: str | None
    owned_certifications: list[str] | None
    target_acquisition_period: str | None
    interest_area: str | None
    weekly_study_hours: str | None
    learning_style: str | None
    monthly_budget: str | None
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


class SourceItem(BaseModel):
    title: str
    url: str


class ConversationMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: Literal["user", "assistant", "system"]
    content: str
    sources: list[SourceItem] = Field(default_factory=list)
    created_at: datetime

    @field_validator("sources", mode="before")
    @classmethod
    def none_to_empty(cls, value):
        return value or []


class ChatMessageCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="사용자 메시지")


class ChatReplyResponse(BaseModel):
    session_id: int
    intent: Literal["recommend", "schedule", "study_path", "general"]
    user_message: ConversationMessageResponse
    assistant_message: ConversationMessageResponse
    # 검색 미설정, 공식 사이트 결과 없음 등 사용자에게 알릴 처리 상태
    notices: list[str]


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
    source_verified: bool
    details: str | None
    fetched_at: datetime
    certification: CertificationSummary


class DashboardResponse(BaseModel):
    session: SessionResponse
    recommendations: list[RecommendationSummary]
    conversation: list[ConversationMessageResponse]
    schedules: list[ScheduleResponse]


class CreateSessionResponse(DashboardResponse):
    session_token: str


class MessageListResponse(BaseModel):
    session_id: int
    items: list[ConversationMessageResponse]


class RecommendationListResponse(BaseModel):
    session_id: int
    items: list[RecommendationSummary]


class ScheduleListResponse(BaseModel):
    session_id: int
    items: list[ScheduleResponse]


class GoogleCalendarStatusResponse(BaseModel):
    connected: bool
    requires_reauthorization: bool = False
    calendar_name: str | None = None


class GoogleCalendarConnectResponse(BaseModel):
    authorization_url: str


class GoogleOAuthCallbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    state: str = Field(min_length=32, max_length=256)
    code: str | None = Field(default=None, min_length=1, max_length=4096)
    error: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def code_or_error_required(self):
        if self.code is None and self.error is None:
            raise ValueError("OAuth callback is incomplete")
        if self.code is not None and self.error is not None:
            raise ValueError("OAuth callback is ambiguous")
        return self


class GoogleOAuthCallbackResponse(BaseModel):
    status: Literal["connected", "cancelled"]


class CalendarEventSyncResponse(BaseModel):
    synced: bool
    event_id: str

