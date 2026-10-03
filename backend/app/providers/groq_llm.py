import logging
from datetime import date

from app.providers.base import (
    CertificationCandidate,
    CoachingPrompt,
    LLMProvider,
    LLMRecommendationResult,
    SearchHit,
    SearchProvider,
)
from app.providers.groq_client import GroqClient, LLMError
from app.providers.web_search import SearchError

logger = logging.getLogger(__name__)

MAX_CANDIDATES = 3
PRIORITIES = ["high", "medium", "low"]

SYSTEM_PROMPT = """너는 처음 자격증 준비를 시작하는 사람을 돕는 자격증 코치다.
사용자 조건을 보고 [자격증 카탈로그]에 있는 자격증 중에서만 최대 {max_candidates}개를 우선순위 순으로 추천한다.
아래 JSON만 출력한다.

{{"assistant_summary": "사용자에게 보여줄 2~3문장 요약",
  "candidates": [
    {{"certification_code": "카탈로그의 code 그대로",
      "match_score": 0~100 숫자,
      "reason": "희망직무·경험과 연결한 추천 이유 1~2문장",
      "study_plan_hint": "목표 취득 시기에 맞춘 학습 조언 1문장"}}
  ]}}

규칙:
- 이미 보유한 자격증은 추천하지 않고, 그 다음 단계 자격증을 우선한다.
- [참고 검색 결과]는 직무 동향 참고용이다. 시험일정·응시료 같은 사실을 summary에 단정하지 않는다.
- 오늘 날짜: {today}"""


class GroqLLMProvider:
    """LLMProvider 구현. Groq 호출 실패 시 fallback provider 결과에 실패 사실을 붙여 반환한다."""

    def __init__(
        self,
        client: GroqClient,
        catalog: list[dict],
        fallback: LLMProvider,
        search: SearchProvider | None = None,
    ):
        self.client = client
        self.catalog = catalog
        self.fallback = fallback
        self.search = search

    def recommend(self, prompt: CoachingPrompt) -> LLMRecommendationResult:
        try:
            raw = self.client.complete_json(self._build_messages(prompt), temperature=0.2)
            return self._parse(raw)
        except LLMError as error:
            logger.warning("Groq 추천 실패, 기본 추천으로 대체: %s", error)
            result = self.fallback.recommend(prompt)
            return LLMRecommendationResult(
                candidates=result.candidates,
                assistant_summary=result.assistant_summary
                + " (AI 추천을 불러오지 못해 기본 규칙으로 추천했어요.)",
            )

    def _build_messages(self, prompt: CoachingPrompt) -> list[dict]:
        catalog_text = "\n".join(
            f"- {item['code']}: {item['name']} ({item['issuer']}) — {item['description']}"
            for item in self.catalog
        )
        user_text = (
            f"[사용자 조건]\n"
            f"희망직무: {prompt.desired_job}\n"
            f"전공 관련 경험: {prompt.major_experience or '입력 없음'}\n"
            f"보유 자격증: {', '.join(prompt.owned_certifications) or '없음'}\n"
            f"목표 취득 시기: {prompt.target_acquisition_period}\n\n"
            f"[자격증 카탈로그]\n{catalog_text}\n\n"
            f"[참고 검색 결과]\n{self._research(prompt)}"
        )
        system = SYSTEM_PROMPT.format(max_candidates=MAX_CANDIDATES, today=date.today().isoformat())
        return [{"role": "system", "content": system}, {"role": "user", "content": user_text}]

    def _research(self, prompt: CoachingPrompt) -> str:
        if self.search is None:
            return "(검색 미사용)"
        try:
            hits = self.search.search(f"{prompt.desired_job} 취업 추천 자격증 {date.today().year}")
        except SearchError as error:
            logger.warning("추천용 검색 실패: %s", error)
            return "(검색 실패)"
        return format_hits(hits)

    def _parse(self, raw: dict) -> LLMRecommendationResult:
        valid_codes = {item["code"] for item in self.catalog}
        candidates: list[CertificationCandidate] = []
        seen: set[str] = set()
        for item in raw.get("candidates") or []:
            code = item.get("certification_code") if isinstance(item, dict) else None
            if code not in valid_codes or code in seen:
                continue
            seen.add(code)
            rank = len(candidates) + 1
            candidates.append(
                CertificationCandidate(
                    certification_code=code,
                    rank=rank,
                    match_score=_clamp_score(item.get("match_score")),
                    priority=PRIORITIES[rank - 1],
                    reason=str(item.get("reason") or ""),
                    study_plan_hint=str(item.get("study_plan_hint") or ""),
                )
            )
            if len(candidates) == MAX_CANDIDATES:
                break

        summary = str(raw.get("assistant_summary") or "")
        if not candidates or not summary:
            raise LLMError(f"추천 응답 형식 오류: {raw}")
        return LLMRecommendationResult(candidates=candidates, assistant_summary=summary)


def _clamp_score(value) -> float:
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def format_hits(hits: list[SearchHit]) -> str:
    if not hits:
        return "(검색 결과 없음)"
    return "\n\n".join(f"[{i}] {h.title} ({h.url})\n{h.content}" for i, h in enumerate(hits, start=1))
