from app.providers.base import CoachingPrompt, CertificationCandidate, LLMRecommendationResult


class MockLLMProvider:
    """Deterministic local provider used until the real LLM integration is supplied."""

    _CATALOG = {
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
            for part in [prompt.desired_job, prompt.major_experience, " ".join(prompt.owned_certifications)]
        ).lower()

        if any(keyword in text for keyword in ["데이터", "data", "분석", "ai", "인공지능"]):
            selected = ["ADSP", "BIGDATA_ENGINEER", "SQLD"]
        elif any(keyword in text for keyword in ["클라우드", "cloud", "devops", "인프라"]):
            selected = ["AWS_SAA", "INFO_PROCESSOR_ENGINEER", "SQLD"]
        elif any(keyword in text for keyword in ["마케팅", "marketing", "조사", "공공"]):
            selected = ["SOCIETY_ANALYST_2", "ADSP", "SQLD"]
        else:
            selected = ["INFO_PROCESSOR_ENGINEER", "SQLD", "AWS_SAA"]

        owned_text = " ".join(prompt.owned_certifications).lower()
        candidates: list[CertificationCandidate] = []
        for rank, code in enumerate(selected, start=1):
            name = self._CATALOG[code]
            already_owned = name.lower() in owned_text or code.lower() in owned_text
            score = max(60.0, 96.0 - ((rank - 1) * 7) - (18 if already_owned else 0))
            priority = "high" if rank == 1 else "medium" if rank == 2 else "low"
            reason = self._reason_for(code, prompt.desired_job, already_owned)
            hint = (
                f"{prompt.target_acquisition_period} 목표라면 주 4~6시간 학습을 권장합니다."
                if not already_owned
                else "이미 보유한 자격증으로 확인되어 갱신·심화 학습 후보로 제안합니다."
            )
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

        summary = (
            f"희망직무 '{prompt.desired_job}'와 목표 시기 '{prompt.target_acquisition_period}'를 기준으로 "
            f"우선순위가 높은 자격증 {len(candidates)}개를 추천했습니다."
        )
        return LLMRecommendationResult(candidates=candidates, assistant_summary=summary)

    @staticmethod
    def _reason_for(code: str, desired_job: str, already_owned: bool) -> str:
        reasons = {
            "INFO_PROCESSOR_ENGINEER": f"{desired_job} 직무의 기본 소프트웨어·시스템 역량을 폭넓게 증명할 수 있습니다.",
            "SQLD": "데이터 조회와 모델링 기초를 증명해 개발·데이터 직무 포트폴리오를 보완합니다.",
            "ADSP": "데이터 이해와 분석 기획 역량을 비교적 짧은 준비 기간에 체계화할 수 있습니다.",
            "BIGDATA_ENGINEER": "분석 프로젝트를 실제 데이터 처리 역량과 연결해 보여주기 좋습니다.",
            "AWS_SAA": "클라우드 아키텍처와 운영 기초를 검증해 백엔드·인프라 직무에 활용할 수 있습니다.",
            "SOCIETY_ANALYST_2": "조사 설계와 통계 분석 역량을 객관적으로 보여줄 수 있습니다.",
        }
        suffix = " 다만 이미 보유 중이라면 다음 단계 자격증을 우선 검토하세요." if already_owned else ""
        return reasons[code] + suffix

