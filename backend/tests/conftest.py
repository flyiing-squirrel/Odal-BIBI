import pytest

from app.api.routes import get_service, settings
from app.main import app
from app.providers.mock_llm import MockLLMProvider
from app.providers.official_schedule import MockOfficialScheduleAdapter, OfficialSiteScheduleProvider
from app.services.coaching import CoachingService


@pytest.fixture(autouse=True)
def mock_coaching_service():
    """.env에 GROQ_API_KEY가 있어도 테스트는 항상 결정론적인 mock 추천을 쓴다."""
    service = CoachingService(
        llm_provider=MockLLMProvider(),
        schedule_provider=OfficialSiteScheduleProvider(MockOfficialScheduleAdapter()),
    )
    app.dependency_overrides[get_service] = lambda: service
    yield
    app.dependency_overrides.pop(get_service, None)


@pytest.fixture(autouse=True)
def relaxed_rate_limits(monkeypatch):
    """테스트마다 세션을 여러 개 만들므로 기본 제한을 넉넉히 둔다. 제한 테스트는 따로 값을 낮춘다."""
    monkeypatch.setattr(settings, "max_sessions_per_window", 1000)
    monkeypatch.setattr(settings, "max_messages_per_window", 1000)
