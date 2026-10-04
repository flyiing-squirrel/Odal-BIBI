from fastapi.testclient import TestClient

from app.api.routes import get_chat_service
from app.main import app
from app.security import require_bff_secret
from app.services.chat import ChatService

PROFILE = {
    "interest_area": "데이터 분석",
    "weekly_study_hours": "주 6시간",
    "learning_style": "프로젝트 중심",
    "monthly_budget": "5만원",
}


def test_browser_session_creates_dashboard_without_database():
    """A browser-owned dashboard is created without opening a database session."""
    app.dependency_overrides[require_bff_secret] = lambda: None
    try:
        response = TestClient(app).post("/api/v1/coaching/browser-session", json=PROFILE)
    finally:
        app.dependency_overrides.pop(require_bff_secret, None)

    assert response.status_code == 201
    body = response.json()
    assert body["session"]["id"] == 1
    assert [item["certification"]["code"] for item in body["recommendations"]] == [
        "ADSP",
        "BIGDATA_ENGINEER",
        "SQLD",
    ]
    assert body["schedules"] == []
    assert [item["role"] for item in body["conversation"]] == ["user", "assistant"]


class ScriptedGroqClient:
    def __init__(self):
        self.responses = [
            {"intent": "general", "search_queries": []},
            {"claims": [], "general_advice": "현재 학습 시간을 고정해 주간 계획부터 시작하세요."},
        ]

    def complete_json(self, messages, **kwargs):
        return self.responses.pop(0)


def test_browser_session_message_returns_reply_without_database():
    app.dependency_overrides[require_bff_secret] = lambda: None
    app.dependency_overrides[get_chat_service] = lambda: ChatService(
        ScriptedGroqClient(), None, history_limit=8
    )
    try:
        response = TestClient(app).post(
            "/api/v1/coaching/browser-session/messages",
            json={
                "profile": PROFILE,
                "conversation": [
                    {
                        "id": 1,
                        "role": "user",
                        "content": "관심 분야: 데이터 분석",
                        "sources": [],
                        "created_at": "2026-10-04T00:00:00Z",
                    },
                    {
                        "id": 2,
                        "role": "assistant",
                        "content": "ADsP를 추천합니다.",
                        "sources": [],
                        "created_at": "2026-10-04T00:00:01Z",
                    },
                ],
                "message": "무엇부터 공부할까?",
            },
        )
    finally:
        app.dependency_overrides.pop(require_bff_secret, None)
        app.dependency_overrides.pop(get_chat_service, None)

    assert response.status_code == 201
    body = response.json()
    assert body["session_id"] == 1
    assert body["user_message"]["id"] == 3
    assert body["assistant_message"]["id"] == 4
    assert body["assistant_message"]["content"] == "현재 학습 시간을 고정해 주간 계획부터 시작하세요."
