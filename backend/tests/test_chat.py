from fastapi.testclient import TestClient

from app.api.routes import get_chat_service, settings
from app.main import app
from app.providers.base import CoachingPrompt, SearchHit
from app.providers.groq_client import LLMError
from app.providers.groq_llm import GroqLLMProvider
from app.providers.mock_llm import MockLLMProvider
from app.services.chat import ChatService
from app.services.coaching import CATALOG
from tests.test_api import override_get_db  # noqa: F401  테스트 DB override 등록


class FakeGroqClient:
    def __init__(self, intent: dict | None = None, answer: str = "", recommend: dict | None = None):
        self.intent = intent
        self.answer = answer
        self.recommend = recommend
        self.calls: list[dict] = []

    def complete_json(self, messages, **kwargs):
        self.calls.append({"messages": messages, "json": True})
        if self.recommend is not None:
            return self.recommend
        return self.intent

    def complete(self, messages, **kwargs):
        self.calls.append({"messages": messages, "json": False})
        return self.answer


class FakeSearch:
    def __init__(self, official_hits: list[SearchHit], general_hits: list[SearchHit]):
        self.official_hits = official_hits
        self.general_hits = general_hits
        self.calls: list[tuple[str, bool]] = []

    def search(self, query, *, official_only=False, max_results=4):
        self.calls.append((query, official_only))
        return self.official_hits if official_only else self.general_hits


PROFILE = {
    "desired_job": "백엔드 개발자",
    "major_experience": "학교 프로젝트에서 REST API를 구현했습니다.",
    "owned_certifications": [],
    "target_acquisition_period": "2026년 하반기",
}


def create_session(client: TestClient) -> tuple[int, dict]:
    """세션을 만들고 (session_id, 토큰 헤더)를 반환."""
    response = client.post("/api/v1/coaching/sessions", json=PROFILE)
    assert response.status_code == 201
    body = response.json()
    return body["session"]["id"], {"X-Session-Token": body["access_token"]}


def test_message_searches_official_first_then_falls_back():
    hit = SearchHit(title="큐넷 시험일정", url="https://www.q-net.or.kr/x", content="2026 정기 기사 3회")
    search = FakeSearch(official_hits=[], general_hits=[hit, hit])
    llm = FakeGroqClient(
        intent={"intent": "schedule", "certificate": "정보처리기사", "search_queries": ["정보처리기사 2026 일정"]},
        answer="다음 회차는 ... [1]",
    )
    app.dependency_overrides[get_chat_service] = lambda: ChatService(llm, search, history_limit=8)
    try:
        client = TestClient(app)
        session_id, headers = create_session(client)
        response = client.post(
            f"/api/v1/coaching/sessions/{session_id}/messages",
            json={"message": "1순위 시험 언제야?"},
            headers=headers,
        )
    finally:
        app.dependency_overrides.pop(get_chat_service, None)

    assert response.status_code == 201
    body = response.json()
    assert body["intent"] == "schedule"
    assert body["assistant_message"]["content"] == "다음 회차는 ... [1]"
    assert body["assistant_message"]["sources"] == [{"title": hit.title, "url": hit.url}]  # 중복 제거
    assert body["notices"] == ["공식 사이트에서 결과를 찾지 못해 일반 검색 결과를 참고했어요."]
    assert search.calls == [("정보처리기사 2026 일정", True), ("정보처리기사 2026 일정", False)]

    # 응답 생성 프롬프트에 세션 프로필·추천 결과·검색 결과가 들어간다
    answer_prompt = llm.calls[-1]["messages"][-1]["content"]
    assert "백엔드 개발자" in answer_prompt and "1순위" in answer_prompt and "큐넷 시험일정" in answer_prompt
    assert "[주의]" not in answer_prompt  # 검색 결과가 있으면 재확인 지시 없음

    conversation = client.get(
        f"/api/v1/coaching/sessions/{session_id}/conversation", headers=headers
    ).json()["items"]
    assert [m["role"] for m in conversation] == ["user", "assistant", "user", "assistant"]
    assert conversation[0]["sources"] == []
    assert conversation[-1]["sources"][0]["url"] == hit.url


def test_message_without_search_provider_adds_notice():
    llm = FakeGroqClient(intent={"intent": "study_path", "search_queries": ["SQLD 교재 추천"]}, answer="답변")
    app.dependency_overrides[get_chat_service] = lambda: ChatService(llm, None, history_limit=8)
    try:
        client = TestClient(app)
        session_id, headers = create_session(client)
        response = client.post(
            f"/api/v1/coaching/sessions/{session_id}/messages", json={"message": "교재?"}, headers=headers
        )
    finally:
        app.dependency_overrides.pop(get_chat_service, None)

    assert response.status_code == 201
    assert response.json()["notices"] == ["검색 기능이 아직 설정되지 않아 검색 없이 답변했어요."]
    # 검색 결과가 없으면 날짜·금액·자료명을 쓰지 말라는 지시가 질문 앞에 붙는다
    assert "[주의]" in llm.calls[-1]["messages"][-1]["content"]


def test_message_without_groq_key_returns_503():
    app.dependency_overrides[get_chat_service] = lambda: ChatService(None, None, history_limit=8)
    try:
        client = TestClient(app)
        session_id, headers = create_session(client)
        response = client.post(
            f"/api/v1/coaching/sessions/{session_id}/messages", json={"message": "안녕"}, headers=headers
        )
    finally:
        app.dependency_overrides.pop(get_chat_service, None)
    assert response.status_code == 503


def test_message_to_missing_session_returns_404():
    llm = FakeGroqClient(intent={"intent": "general", "search_queries": []}, answer="")
    app.dependency_overrides[get_chat_service] = lambda: ChatService(llm, None, history_limit=8)
    try:
        response = TestClient(app).post(
            "/api/v1/coaching/sessions/999999/messages",
            json={"message": "안녕"},
            headers={"X-Session-Token": "x"},
        )
    finally:
        app.dependency_overrides.pop(get_chat_service, None)
    assert response.status_code == 404


PROMPT = CoachingPrompt(
    desired_job="데이터 분석가",
    major_experience=None,
    owned_certifications=[],
    target_acquisition_period="2027년 상반기",
)


def test_groq_recommend_keeps_only_catalog_codes():
    llm = FakeGroqClient(
        recommend={
            "assistant_summary": "데이터 직무 기준 추천입니다.",
            "candidates": [
                {"certification_code": "ADSP", "match_score": 120, "reason": "r1", "study_plan_hint": "h1"},
                {"certification_code": "NOT_IN_CATALOG", "match_score": 90, "reason": "x", "study_plan_hint": "x"},
                {"certification_code": "ADSP", "match_score": 80, "reason": "dup", "study_plan_hint": "dup"},
                {"certification_code": "SQLD", "match_score": "85", "reason": "r2", "study_plan_hint": "h2"},
            ],
        }
    )
    result = GroqLLMProvider(llm, CATALOG, fallback=MockLLMProvider()).recommend(PROMPT)

    assert [c.certification_code for c in result.candidates] == ["ADSP", "SQLD"]
    assert [c.rank for c in result.candidates] == [1, 2]
    assert [c.priority for c in result.candidates] == ["high", "medium"]
    assert result.candidates[0].match_score == 100.0
    assert result.assistant_summary == "데이터 직무 기준 추천입니다."


def test_groq_recommend_falls_back_on_error():
    class FailingClient:
        def complete_json(self, messages, **kwargs):
            raise LLMError("boom")

    result = GroqLLMProvider(FailingClient(), CATALOG, fallback=MockLLMProvider()).recommend(PROMPT)
    assert result.candidates[0].certification_code == "ADSP"  # mock 규칙 추천
    assert "기본 규칙으로 추천" in result.assistant_summary


class ScriptedGroqClient(FakeGroqClient):
    """complete()가 호출될 때마다 answers를 순서대로 반환."""

    def __init__(self, intent: dict, answers: list[str]):
        super().__init__(intent=intent)
        self.answers = answers

    def complete(self, messages, **kwargs):
        self.calls.append({"messages": messages, "json": False})
        return self.answers.pop(0)


def ask(llm, search=None) -> dict:
    app.dependency_overrides[get_chat_service] = lambda: ChatService(llm, search, history_limit=8)
    try:
        client = TestClient(app)
        session_id, headers = create_session(client)
        response = client.post(
            f"/api/v1/coaching/sessions/{session_id}/messages", json={"message": "응시료?"}, headers=headers
        )
    finally:
        app.dependency_overrides.pop(get_chat_service, None)
    assert response.status_code == 201
    return response.json()


def test_unsourced_price_is_rewritten():
    llm = ScriptedGroqClient(
        intent={"intent": "schedule", "search_queries": ["ADsP 응시료"]},
        answers=["응시료는 보통 5~7만원이에요.", "미확인 — 주관기관 공식 사이트에서 확인하세요."],
    )
    body = ask(llm)
    assert body["assistant_message"]["content"] == "미확인 — 주관기관 공식 사이트에서 확인하세요."
    assert "5~7만원" in llm.calls[-1]["messages"][-1]["content"]  # 재작성 요청에 문제 표현 전달


def test_unsourced_fact_lines_removed_when_rewrite_fails():
    llm = ScriptedGroqClient(
        intent={"intent": "schedule", "search_queries": ["ADsP 일정"]},
        answers=["시험은 연 2회예요.\n공식 사이트에서 확인하세요.", "접수는 4~5월이에요.\n공식 사이트에서 확인하세요."],
    )
    body = ask(llm)
    assert body["assistant_message"]["content"] == "공식 사이트에서 확인하세요."


HITS = [
    SearchHit(title="ADsP 시험안내", url="https://www.dataq.or.kr/a", content="응시료 50,000원"),
    SearchHit(title="ADsP 일정", url="https://www.dataq.or.kr/b", content="제50회 8월 시행"),
]


def test_cited_facts_with_search_results_pass_unchanged():
    answer = "응시료는 50,000원이에요 [1].\n다음 시험은 8월이에요 [2].\n공부는 기출 위주로 하세요."
    llm = ScriptedGroqClient(intent={"intent": "schedule", "search_queries": ["ADsP 응시료"]}, answers=[answer])
    body = ask(llm, FakeSearch(official_hits=HITS, general_hits=[]))
    assert body["assistant_message"]["content"] == answer
    assert len([c for c in llm.calls if not c["json"]]) == 1  # 재작성 요청 없음


def test_uncited_fact_with_search_results_is_rewritten():
    llm = ScriptedGroqClient(
        intent={"intent": "schedule", "search_queries": ["ADsP 응시료"]},
        answers=["응시료는 50,000원이에요.", "응시료는 50,000원이에요 [1]."],
    )
    body = ask(llm, FakeSearch(official_hits=HITS, general_hits=[]))
    assert body["assistant_message"]["content"] == "응시료는 50,000원이에요 [1]."
    retry_prompt = llm.calls[-1]["messages"][-1]["content"]
    assert "50,000원" in retry_prompt and "[1]~[2]" in retry_prompt


def test_out_of_range_citation_line_removed_when_rewrite_fails():
    llm = ScriptedGroqClient(
        intent={"intent": "schedule", "search_queries": ["ADsP 일정"]},
        answers=[
            "시험은 11월이에요 [3].\n공식 사이트에서 확인하세요 [1].",
            "시험은 2026.11.15예요 [5].\n공식 사이트에서 확인하세요 [1].",
        ],
    )
    body = ask(llm, FakeSearch(official_hits=HITS, general_hits=[]))
    assert body["assistant_message"]["content"] == "공식 사이트에서 확인하세요 [1]."
    assert "[3]" in llm.calls[-1]["messages"][-1]["content"]


def test_unsourced_url_without_search_is_removed():
    llm = ScriptedGroqClient(
        intent={"intent": "study_path", "search_queries": ["ADsP 교재"]},
        answers=["교재는 https://example.com/book 참고.\n기출을 반복하세요.", "https://example.com/book\n기출을 반복하세요."],
    )
    body = ask(llm)
    assert body["assistant_message"]["content"] == "기출을 반복하세요."


def test_messages_are_rate_limited_per_session(monkeypatch):
    monkeypatch.setattr(settings, "max_messages_per_window", 2)
    llm = FakeGroqClient(intent={"intent": "general", "search_queries": []}, answer="안녕하세요")
    app.dependency_overrides[get_chat_service] = lambda: ChatService(llm, None, history_limit=8)
    try:
        client = TestClient(app)
        session_id, headers = create_session(client)
        url = f"/api/v1/coaching/sessions/{session_id}/messages"
        codes = [client.post(url, json={"message": "안녕"}, headers=headers).status_code for _ in range(3)]
    finally:
        app.dependency_overrides.pop(get_chat_service, None)
    assert codes == [201, 201, 429]
