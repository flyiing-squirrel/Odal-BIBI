from dataclasses import dataclass, field
from datetime import date
from typing import Protocol


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
