from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app


TEST_DB = Path(__file__).parent / "test.sqlite3"
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


def test_create_and_read_dashboard():
    client = TestClient(app)
    response = client.post(
        "/api/v1/coaching/sessions",
        json={
            "desired_job": "백엔드 개발자",
            "major_experience": "학교 프로젝트에서 REST API를 구현했습니다.",
            "owned_certifications": [],
            "target_acquisition_period": "2026년 하반기",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["session"]["id"] > 0
    assert len(body["recommendations"]) == 3
    assert len(body["conversation"]) == 2
    assert len(body["schedules"]) == 9

    session_id = body["session"]["id"]
    recommendation_id = body["recommendations"][0]["id"]
    schedule_id = body["schedules"][0]["id"]

    assert client.get(f"/api/v1/coaching/sessions/{session_id}").status_code == 200
    assert (
        client.get(
            f"/api/v1/coaching/sessions/{session_id}/recommendations/{recommendation_id}"
        ).status_code
        == 200
    )
    assert (
        client.get(f"/api/v1/coaching/sessions/{session_id}/schedules/{schedule_id}").status_code
        == 200
    )


def test_missing_session_returns_404():
    client = TestClient(app)
    response = client.get("/api/v1/coaching/sessions/999999")
    assert response.status_code == 404

