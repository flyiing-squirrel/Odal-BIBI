from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes import settings
from app.db import Base, get_db
from app.main import app


TEST_DB = Path(__file__).parent / "test.sqlite3"
TEST_DB.unlink(missing_ok=True)  # 모델 컬럼이 바뀌어도 매번 새 스키마로 시작
engine = create_engine(f"sqlite:///{TEST_DB}", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


PROFILE = {
    "desired_job": "백엔드 개발자",
    "major_experience": "학교 프로젝트에서 REST API를 구현했습니다.",
    "owned_certifications": [],
    "target_acquisition_period": "2026년 하반기",
}


def test_create_and_read_dashboard():
    client = TestClient(app)
    response = client.post("/api/v1/coaching/sessions", json=PROFILE)
    assert response.status_code == 201
    body = response.json()
    assert body["session"]["id"] > 0
    assert len(body["recommendations"]) == 3
    assert len(body["conversation"]) == 2
    assert len(body["schedules"]) == 9

    session_id = body["session"]["id"]
    recommendation_id = body["recommendations"][0]["id"]
    schedule_id = body["schedules"][0]["id"]
    headers = {"X-Session-Token": body["access_token"]}

    assert client.get(f"/api/v1/coaching/sessions/{session_id}", headers=headers).status_code == 200
    assert (
        client.get(
            f"/api/v1/coaching/sessions/{session_id}/recommendations/{recommendation_id}",
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/coaching/sessions/{session_id}/schedules/{schedule_id}", headers=headers
        ).status_code
        == 200
    )


def test_missing_session_returns_404():
    client = TestClient(app)
    response = client.get("/api/v1/coaching/sessions/999999", headers={"X-Session-Token": "x"})
    assert response.status_code == 404


def create_session(client: TestClient) -> tuple[int, str]:
    response = client.post("/api/v1/coaching/sessions", json=PROFILE)
    assert response.status_code == 201
    body = response.json()
    return body["session"]["id"], body["access_token"]


def test_session_requires_token():
    client = TestClient(app)
    session_id, _ = create_session(client)
    assert client.get(f"/api/v1/coaching/sessions/{session_id}").status_code == 401


def test_other_sessions_token_is_rejected_as_not_found():
    client = TestClient(app)
    first_id, _ = create_session(client)
    _, second_token = create_session(client)
    for path in ["", "/recommendations", "/conversation", "/schedules"]:
        response = client.get(
            f"/api/v1/coaching/sessions/{first_id}{path}", headers={"X-Session-Token": second_token}
        )
        assert response.status_code == 404
    response = client.post(
        f"/api/v1/coaching/sessions/{first_id}/messages",
        json={"message": "안녕"},
        headers={"X-Session-Token": second_token},
    )
    assert response.status_code == 404


def test_session_creation_is_rate_limited_per_ip(monkeypatch):
    monkeypatch.setattr(settings, "max_sessions_per_window", 2)
    client = TestClient(app)
    headers = {"X-Forwarded-For": "203.0.113.7"}
    assert client.post("/api/v1/coaching/sessions", json=PROFILE, headers=headers).status_code == 201
    assert client.post("/api/v1/coaching/sessions", json=PROFILE, headers=headers).status_code == 201
    assert client.post("/api/v1/coaching/sessions", json=PROFILE, headers=headers).status_code == 429
    other = {"X-Forwarded-For": "203.0.113.8"}
    assert client.post("/api/v1/coaching/sessions", json=PROFILE, headers=other).status_code == 201

