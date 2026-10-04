from typing import ClassVar

from app.providers.base import CertificationCandidate, CoachingPrompt, LLMRecommendationResult


class MockLLMProvider:
    """Deterministic local provider used until the real LLM integration is supplied."""

    _CATALOG: ClassVar[dict[str, str]] = {
        "INFO_PROCESSOR_ENGINEER": "정보처리기사",
        "SQLD": "SQLD",
        "ADSP": "ADsP",
        "BIGDATA_ENGINEER": "빅데이터분석기사",
        "AWS_SAA": "AWS Certified Solutions Architect - Associate",
        "SOCIETY_ANALYST_2": "사회조사분석사 2급",
    }

    def recommend(self, prompt: CoachingPrompt) -> LLMRecommendationResult:
        text = " ".join(
            part or ""
            for part in [
                prompt.interest_area,
                prompt.weekly_study_hours,
                prompt.learning_style,
                prompt.monthly_budget,
                prompt.desired_job,
                prompt.major_experience,
                " ".join(prompt.owned_certifications),
            ]
        ).lower()

        if any(keyword in text for keyword in ["데이터", "data", "분석", "ai", "인공지능"]):
            selected = ["ADSP", "BIGDATA_ENGINEER", "SQLD"]
        elif any(keyword in text for keyword in ["클라우드", "cloud", "devops", "인프라"]):
            selected = ["AWS_SAA", "INFO_PROCESSOR_ENGINEER", "SQLD"]
        elif any(keyword in text for keyword in ["마케팅", "marketing", "조사", "공공"]):
            selected = ["SOCIETY_ANALYST_2", "ADSP", "SQLD"]
        else:
            selected = ["INFO_PROCESSOR_ENGINEER", "SQLD", "AWS_SAA"]

        owned_text = " ".join(prompt.owned_certifications or []).lower()
        candidates: list[CertificationCandidate] = []
        interest_area = prompt.interest_area or prompt.desired_job or "관심 분야"
        for rank, code in enumerate(selected, start=1):
            name = self._CATALOG[code]
            already_owned = name.lower() in owned_text or code.lower() in owned_text
            score = max(60.0, 96.0 - ((rank - 1) * 7) - (18 if already_owned else 0))
            priority = "high" if rank == 1 else "medium" if rank == 2 else "low"
            reason = self._reason_for(code, interest_area, already_owned)
            if already_owned:
                hint = "이미 보유한 자격증으로 확인되어 갱신·심화 학습 후보로 제안합니다."
            elif prompt.weekly_study_hours:
                hint = f"주간 학습 시간 {prompt.weekly_study_hours}을 고려해 학습 계획을 세워보세요."
            else:
                hint = "현재 가능한 학습 시간을 기준으로 주간 계획을 세워보세요."
            candidates.append(
                CertificationCandidate(
                    certification_code=code,
                    rank=rank,
                    match_score=score,
                    priority=priority,
                    reason=reason,
                    study_plan_hint=hint,
                )
            )

        summary = f"관심 분야 '{interest_area}'와 학습 여건을 기준으로 자격증 {len(candidates)}개를 추천했습니다."
        return LLMRecommendationResult(candidates=candidates, assistant_summary=summary)

    @staticmethod
    def _reason_for(code: str, interest_area: str, already_owned: bool) -> str:
        reasons = {
            "INFO_PROCESSOR_ENGINEER": f"{interest_area} 분야의 기본 소프트웨어·시스템 역량을 폭넓게 증명할 수 있습니다.",
            "SQLD": "데이터 조회와 모델링 기초를 증명해 개발·데이터 직무 포트폴리오를 보완합니다.",
            "ADSP": "데이터 이해와 분석 기획 역량을 비교적 짧은 준비 기간에 체계화할 수 있습니다.",
            "BIGDATA_ENGINEER": "분석 프로젝트를 실제 데이터 처리 역량과 연결해 보여주기 좋습니다.",
            "AWS_SAA": "클라우드 아키텍처와 운영 기초를 검증해 백엔드·인프라 직무에 활용할 수 있습니다.",
            "SOCIETY_ANALYST_2": "조사 설계와 통계 분석 역량을 객관적으로 보여줄 수 있습니다.",
        }
        suffix = " 다만 이미 보유 중이라면 다음 단계 자격증을 우선 검토하세요." if already_owned else ""
        return reasons[code] + suffix

