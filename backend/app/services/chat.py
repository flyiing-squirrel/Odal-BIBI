import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import CertificationRecommendation, CoachingSession, ConversationMessage
from app.providers.base import SearchHit, SearchProvider
from app.providers.groq_client import GroqClient
from app.providers.groq_llm import format_hits
from app.providers.web_search import SearchError

logger = logging.getLogger(__name__)

INTENT_PROMPT = """너는 자격증 코치 서비스의 요청 분석기다. 사용자 메시지를 읽고 아래 JSON만 출력한다.

{{"intent": "recommend" | "schedule" | "study_path" | "general",
  "certificate": "언급된 자격증 정식 명칭 또는 null",
  "search_queries": ["웹 검색어", ...]}}

intent 기준:
- recommend: 어떤 자격증을 따야 할지 추천·비교 요청
- schedule: 시험일정, 접수기간, 응시료, 응시자격, 합격발표 문의
- study_path: 강의, 교재, 기출, 공부법, 학습 기간 문의
- general: 인사, 서비스 사용법 등 검색이 필요 없는 대화

search_queries 규칙:
- 검색이 필요 없으면 빈 배열
- 최대 2개, 한국어, 구체적으로 (자격증명 + 알고 싶은 항목)
- 일정 관련이면 연도({year})를 포함
- "그거", "1순위" 같은 지시어는 [사용자 정보]와 이전 대화를 보고 실제 자격증명으로 바꾼다

오늘 날짜: {today}"""

ANSWER_PROMPT = """너는 처음 자격증 준비를 시작하는 사람을 돕는 자격증 코치다. 한국어로 답한다.

형식:
- 핵심만 15줄 이내. 표·이모지·제목(#)은 쓰지 않고, 필요하면 짧은 목록만 쓴다.

사실 규칙 (가장 중요):
1. 날짜(시험일·접수기간·발표일), 금액(응시료·강의·교재 가격), 응시자격, 교재·강의·자료의 구체적 이름, URL은 [검색 결과]에 그대로 있는 것만 쓰고 문장 끝에 [1]처럼 출처 번호를 붙인다.
2. [검색 결과]에 없는 위 항목은 "약", "보통" 같은 추정으로도 쓰지 않는다. "미확인"이라고 쓰고 주관기관 이름만 안내한다 (URL을 지어내지 않는다).
3. 오늘 날짜 기준으로 이미 지난 회차는 "지난 회차"로 표시하고 다음 회차를 우선 안내한다.
4. 뉴스·블로그 출처는 공식 근거가 아님을 밝힌다.
5. [사용자 정보]의 희망직무·목표 시기·추천 결과에 맞춰 답한다.

오늘 날짜: {today}"""

# 검색 결과가 없을 때 질문 바로 앞에 붙이는 재확인 지시 (시스템 프롬프트만으로는 모델이 가격을 추정하는 경우가 있었음)
NO_SOURCES_REMINDER = (
    "[주의] 이번에는 검색 결과가 없다. 날짜·금액·교재/강의 이름·URL을 하나도 쓰지 말고, "
    "학습 순서·방법 같은 일반적인 조언만 한다. 필요한 사실은 \"미확인 — 주관기관 공식 사이트에서 확인\"으로 쓴다."
)

# 출처 번호 없이 나오면 안 되는 표현: 금액, 월 단위·숫자형 날짜, 연 N회, URL
FACT_PATTERN = re.compile(
    r"\d[\d,]*\s*(?:~\s*\d[\d,]*\s*)?(?:만\s*)?원"
    r"|\d{1,2}\s*(?:~\s*\d{1,2}\s*)?월"
    r"|\d{4}\s*[-./]\s*\d{1,2}\s*[-./]\s*\d{1,2}"
    r"|연\s*\d+\s*(?:~\s*\d+\s*)?회"
    r"|https?://\S+"
)
CITATION_PATTERN = re.compile(r"\[(\d+)\]")


def ungrounded_parts(line: str, hit_count: int) -> list[str]:
    """줄에서 근거가 없는 표현을 반환한다.

    - 검색 결과 범위를 벗어난 출처 번호 [n]은 항상 문제다.
    - 사실 표현(FACT_PATTERN)이 있는 줄은 범위 안의 출처 번호가 하나 이상 있어야 한다.
      검색 결과가 없으면(hit_count=0) 유효한 번호가 있을 수 없으므로 사실 표현 자체가 문제다.
    """
    citations = [int(n) for n in CITATION_PATTERN.findall(line)]
    invalid = [f"[{n}]" for n in citations if not 1 <= n <= hit_count]
    has_valid = any(1 <= n <= hit_count for n in citations)
    facts = [] if has_valid else [m.group() for m in FACT_PATTERN.finditer(line)]
    return invalid + facts


class IntentResult(BaseModel):
    intent: str = Field(default="general", pattern="^(recommend|schedule|study_path|general)$")
    certificate: str | None = None
    search_queries: list[str] = Field(default_factory=list, max_length=2)


class ChatNotConfiguredError(RuntimeError):
    """GROQ_API_KEY가 비어 있어 대화 기능을 쓸 수 없음."""


@dataclass
class ChatResult:
    intent: str
    user_message: ConversationMessage
    assistant_message: ConversationMessage
    notices: list[str] = field(default_factory=list)


class ChatService:
    """세션 대화 이어가기: 요청 파악 → 검색 → 검색 결과 근거로 응답 생성."""

    def __init__(self, client: GroqClient | None, search: SearchProvider | None, history_limit: int):
        self.client = client
        self.search = search
        self.history_limit = history_limit

    def reply(self, db: Session, session_id: int, message: str) -> ChatResult:
        if self.client is None:
            raise ChatNotConfiguredError("GROQ_API_KEY가 설정되지 않았습니다. .env에 키를 넣어주세요.")

        session = self._get_session(db, session_id)
        context = self._user_context(session)
        history = [{"role": m.role, "content": m.content} for m in session.messages[-self.history_limit :]]
        notices: list[str] = []

        intent = self._analyze(message, context, history)
        hits = self._search(intent, notices)
        messages = self._answer_messages(message, context, history, intent, hits)
        answer = self.client.complete(messages, max_tokens=1500)
        answer = self._enforce_grounding(messages, answer, len(hits))

        user_message = ConversationMessage(session_id=session.id, role="user", content=message)
        assistant_message = ConversationMessage(
            session_id=session.id,
            role="assistant",
            content=answer,
            sources=[{"title": h.title, "url": h.url} for h in hits],
        )
        db.add_all([user_message, assistant_message])
        db.commit()
        return ChatResult(intent.intent, user_message, assistant_message, notices)

    def _analyze(self, message: str, context: str, history: list[dict]) -> IntentResult:
        today = date.today()
        messages = [
            {"role": "system", "content": INTENT_PROMPT.format(today=today.isoformat(), year=today.year)},
            *history,
            {"role": "user", "content": f"[사용자 정보]\n{context}\n\n[메시지]\n{message}"},
        ]
        raw = self.client.complete_json(messages, temperature=0)
        try:
            return IntentResult.model_validate(raw)
        except ValidationError as error:
            # 형식이 어긋나도 대화는 이어가도록 메시지 자체를 검색어로 쓴다
            logger.warning("의도 분석 결과 형식 오류: %s / raw=%s", error, raw)
            return IntentResult(intent="general", search_queries=[message[:100]])

    def _enforce_grounding(self, messages: list[dict], answer: str, hit_count: int) -> str:
        """근거 없는 금액·날짜·URL·출처 번호가 있으면 한 번 다시 쓰게 하고, 그래도 남으면 해당 줄을 지운다."""
        found = [part for line in answer.splitlines() for part in ungrounded_parts(line, hit_count)]
        if not found:
            return answer
        logger.warning("근거 없는 표현 감지, 재작성 요청: %s", found)
        instruction = (
            f"검색 근거가 없는 표현이 있다: {', '.join(found)}. "
            + (
                f"사실 표현에는 [1]~[{hit_count}] 중 실제 근거가 되는 출처 번호를 붙이고, 근거가 없으면 그 내용을 빼고 "
                if hit_count
                else "이 표현이 들어간 내용을 빼고 "
            )
            + "같은 형식으로 답변 전체를 다시 써라."
        )
        retry = [*messages, {"role": "assistant", "content": answer}, {"role": "user", "content": instruction}]
        answer = self.client.complete(retry, max_tokens=1500)
        lines = answer.splitlines()
        kept = [line for line in lines if not ungrounded_parts(line, hit_count)]
        if len(kept) != len(lines):
            logger.warning("재작성 후에도 근거 없는 표현이 남아 해당 줄 제거")
        return "\n".join(kept)

    def _search(self, intent: IntentResult, notices: list[str]) -> list[SearchHit]:
        if not intent.search_queries:
            return []
        if self.search is None:
            notices.append("검색 기능이 아직 설정되지 않아 검색 없이 답변했어요.")
            return []

        hits: list[SearchHit] = []
        if intent.intent == "schedule":
            hits = self._run_queries(intent.search_queries, notices, official_only=True)
            if not hits:
                notices.append("공식 사이트에서 결과를 찾지 못해 일반 검색 결과를 참고했어요.")
        if not hits:
            hits = self._run_queries(intent.search_queries, notices, official_only=False)
        return hits

    def _run_queries(self, queries: list[str], notices: list[str], *, official_only: bool) -> list[SearchHit]:
        hits: list[SearchHit] = []
        seen: set[str] = set()
        for query in queries:
            try:
                results = self.search.search(query, official_only=official_only)
            except SearchError as error:
                logger.warning("%s", error)
                notices.append(f"일부 검색에 실패했어요: {query}")
                continue
            for hit in results:
                if hit.url not in seen:
                    seen.add(hit.url)
                    hits.append(hit)
        return hits

    @staticmethod
    def _answer_messages(
        message: str, context: str, history: list[dict], intent: IntentResult, hits: list[SearchHit]
    ) -> list[dict]:
        user_text = (
            f"[사용자 정보]\n{context}\n\n"
            f"[요청 분석]\n의도: {intent.intent} / 자격증: {intent.certificate or '없음'}\n\n"
            f"[검색 결과]\n{format_hits(hits)}\n\n"
            + (f"{NO_SOURCES_REMINDER}\n\n" if not hits else "")
            + f"[질문]\n{message}"
        )
        return [
            {"role": "system", "content": ANSWER_PROMPT.format(today=date.today().isoformat())},
            *history,
            {"role": "user", "content": user_text},
        ]

    @staticmethod
    def _user_context(session: CoachingSession) -> str:
        recommended = ", ".join(
            f"{r.rank}순위 {r.certification.name}" for r in session.recommendations
        )
        return json.dumps(
            {
                "희망직무": session.desired_job,
                "전공 관련 경험": session.major_experience,
                "보유 자격증": session.owned_certifications,
                "목표 취득 시기": session.target_acquisition_period,
                "추천 결과": recommended or None,
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _get_session(db: Session, session_id: int) -> CoachingSession:
        session = db.scalar(
            select(CoachingSession)
            .where(CoachingSession.id == session_id)
            .options(
                selectinload(CoachingSession.messages),
                selectinload(CoachingSession.recommendations).selectinload(
                    CertificationRecommendation.certification
                ),
            )
        )
        if session is None:
            raise LookupError("Coaching session not found")
        return session
