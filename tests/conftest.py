import pytest

from app.api.routes import get_service
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
