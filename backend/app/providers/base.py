from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Annotated, Protocol

from pydantic import BaseModel, ConfigDict, Field


@dataclass(frozen=True)
class CoachingPrompt:
    # Legacy fields remain optional so existing provider callers can transition safely.
    desired_job: str | None = None
    major_experience: str | None = None
    owned_certifications: list[str] = field(default_factory=list)
    target_acquisition_period: str | None = None
    interest_area: str | None = None
    weekly_study_hours: str | None = None
    learning_style: str | None = None
    monthly_budget: str | None = None


@dataclass(frozen=True)
class CertificationCandidate:
    certification_code: str
    rank: int
    match_score: float
    priority: str
    reason: str
    study_plan_hint: str


@dataclass(frozen=True)
class LLMRecommendationResult:
    candidates: list[CertificationCandidate]
    assistant_summary: str


class LLMProvider(Protocol):
    def recommend(self, prompt: CoachingPrompt) -> LLMRecommendationResult:
        """Generate recommendations and a human-readable answer."""


@dataclass(frozen=True)
class ScheduleRecord:
    exam_name: str
    registration_start: date | None
    registration_end: date | None
    exam_date: date
    result_date: date | None
    status: str
    source_name: str
    source_url: str
    details: str | None = None
    source_verified: bool = False


class ScheduleProvider(Protocol):
    def get_schedules(self, certification_code: str, target_period: str | None) -> list[ScheduleRecord]:
        """Return schedules from an official-site adapter or another trusted source."""


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    content: str


class SearchProvider(Protocol):
    def search(self, query: str, *, official_only: bool = False, max_results: int = 4) -> list[SearchHit]:
        """Return web search results. official_only restricts to official issuer domains."""


class ClaimType(StrEnum):
    GENERAL_ADVICE = "general_advice"
    DATE = "date"
    FEE = "fee"
    ELIGIBILITY = "eligibility"
    RESOURCE = "resource"
    OTHER_FACT = "other_fact"


class EvidenceClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=1200)
    source_ids: list[Annotated[int, Field(strict=True, ge=0, le=7)]] = Field(
        default_factory=list, max_length=3
    )
    claim_type: ClaimType


class GeneratedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    claims: list[EvidenceClaim] = Field(default_factory=list, max_length=6)
    general_advice: str | None = Field(default=None, max_length=2000)


class VerificationResult(StrEnum):
    SUPPORTED = "supported"
    UNCERTAIN = "uncertain"
    UNSUPPORTED = "unsupported"
