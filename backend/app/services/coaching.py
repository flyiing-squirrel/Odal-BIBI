from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Certification,
    CertificationRecommendation,
    CertificationSchedule,
    CoachingSession,
    ConversationMessage,
)
from app.providers.base import CoachingPrompt, LLMProvider, ScheduleProvider
from app.schemas import DashboardResponse

CATALOG = [
    {
        "code": "INFO_PROCESSOR_ENGINEER",
        "name": "정보처리기사",
        "issuer": "한국산업인력공단",
        "description": "소프트웨어 설계·개발·데이터베이스·프로그래밍 역량을 종합적으로 검증하는 국가기술자격입니다.",
        "official_url": "https://www.q-net.or.kr/crf005.do?id=crf00503&jmCd=1320",
    },
    {
        "code": "SQLD",
        "name": "SQLD",
        "issuer": "한국데이터산업진흥원",
        "description": "데이터 모델링과 SQL 기본·활용 역량을 검증하는 자격입니다.",
        "official_url": "https://www.dataq.or.kr/www/accept/schedule.do",
    },
    {
        "code": "ADSP",
        "name": "ADsP",
        "issuer": "한국데이터산업진흥원",
        "description": "데이터 이해, 분석 기획, 데이터 분석 기초 역량을 검증하는 자격입니다.",
        "official_url": "https://www.dataq.or.kr/www/accept/schedule.do",
    },
    {
        "code": "BIGDATA_ENGINEER",
        "name": "빅데이터분석기사",
        "issuer": "한국산업인력공단",
        "description": "빅데이터 분석 기획부터 수집·처리·분석·시각화까지의 실무 역량을 검증합니다.",
        "official_url": "https://www.q-net.or.kr/crf005.do?id=crf00503&jmCd=1321",
    },
    {
        "code": "AWS_SAA",
        "name": "AWS Certified Solutions Architect - Associate",
        "issuer": "Amazon Web Services",
        "description": "AWS 기반의 보안성·복원력·고성능·비용 효율적 아키텍처 설계 역량을 검증합니다.",
        "official_url": "https://aws.amazon.com/certification/certified-solutions-architect-associate/",
    },
    {
        "code": "SOCIETY_ANALYST_2",
        "name": "사회조사분석사 2급",
        "issuer": "한국산업인력공단",
        "description": "사회조사 설계, 자료 수집, 통계 분석 역량을 검증하는 국가기술자격입니다.",
        "official_url": "https://www.q-net.or.kr/crf005.do?id=crf00503&jmCd=1740",
    },
]


class CoachingService:
    def __init__(self, llm_provider: LLMProvider, schedule_provider: ScheduleProvider):
        self.llm_provider = llm_provider
        self.schedule_provider = schedule_provider

    def create_session(
        self,
        db: Session,
        desired_job: str,
        major_experience: str | None,
        owned_certifications: list[str],
        target_acquisition_period: str,
    ) -> DashboardResponse:
        session = CoachingSession(
            desired_job=desired_job,
            major_experience=major_experience,
            owned_certifications=owned_certifications,
            target_acquisition_period=target_acquisition_period,
        )
        db.add(session)
        db.flush()

        prompt = CoachingPrompt(
            desired_job=desired_job,
            major_experience=major_experience,
            owned_certifications=owned_certifications,
            target_acquisition_period=target_acquisition_period,
        )
        result = self.llm_provider.recommend(prompt)
        db.add(
            ConversationMessage(
                session_id=session.id,
                role="user",
                content=(
                    f"희망직무: {desired_job}\n"
                    f"전공 관련 경험: {major_experience or '입력 없음'}\n"
                    f"보유 자격증: {', '.join(owned_certifications) or '없음'}\n"
                    f"목표 취득 시기: {target_acquisition_period}"
                ),
            )
        )
        db.add(ConversationMessage(session_id=session.id, role="assistant", content=result.assistant_summary))

        catalog_by_code = {item.code: item for item in db.scalars(select(Certification)).all()}
        for candidate in result.candidates:
            certification = catalog_by_code.get(candidate.certification_code)
            if certification is None:
                continue
            recommendation = CertificationRecommendation(
                session_id=session.id,
                certification_id=certification.id,
                rank=candidate.rank,
                match_score=candidate.match_score,
                priority=candidate.priority,
                reason=candidate.reason,
                study_plan_hint=candidate.study_plan_hint,
            )
            db.add(recommendation)
            db.flush()
            for schedule in self.schedule_provider.get_schedules(
                certification.code, target_acquisition_period
            ):
                db.add(
                    CertificationSchedule(
                        session_id=session.id,
                        recommendation_id=recommendation.id,
                        certification_id=certification.id,
                        exam_name=schedule.exam_name,
                        registration_start=schedule.registration_start,
                        registration_end=schedule.registration_end,
                        exam_date=schedule.exam_date,
                        result_date=schedule.result_date,
                        status=schedule.status,
                        source_name=schedule.source_name,
                        source_url=schedule.source_url,
                        details=schedule.details,
                    )
                )

        db.commit()
        return self.get_dashboard(db, session.id)

    def get_dashboard(self, db: Session, session_id: int) -> DashboardResponse:
        session = self._get_session(db, session_id)
        return DashboardResponse(
            session=session,
            recommendations=session.recommendations,
            conversation=session.messages,
            schedules=session.schedules,
        )

    def get_recommendations(self, db: Session, session_id: int) -> list[CertificationRecommendation]:
        session = self._get_session(db, session_id)
        return list(session.recommendations)

    def get_recommendation(
        self, db: Session, session_id: int, recommendation_id: int
    ) -> CertificationRecommendation:
        self._get_session(db, session_id)
        recommendation = db.scalar(
            select(CertificationRecommendation)
            .where(
                CertificationRecommendation.id == recommendation_id,
                CertificationRecommendation.session_id == session_id,
            )
            .options(
                selectinload(CertificationRecommendation.certification),
                selectinload(CertificationRecommendation.schedules).selectinload(
                    CertificationSchedule.certification
                ),
            )
        )
        if recommendation is None:
            raise LookupError("Recommendation not found")
        return recommendation

    def get_messages(self, db: Session, session_id: int) -> list[ConversationMessage]:
        session = self._get_session(db, session_id)
        return list(session.messages)

    def get_message(self, db: Session, session_id: int, message_id: int) -> ConversationMessage:
        self._get_session(db, session_id)
        message = db.scalar(
            select(ConversationMessage).where(
                ConversationMessage.id == message_id,
                ConversationMessage.session_id == session_id,
            )
        )
        if message is None:
            raise LookupError("Conversation message not found")
        return message

    def get_schedules(self, db: Session, session_id: int) -> list[CertificationSchedule]:
        session = self._get_session(db, session_id)
        return list(session.schedules)

    def get_schedule(self, db: Session, session_id: int, schedule_id: int) -> CertificationSchedule:
        self._get_session(db, session_id)
        schedule = db.scalar(
            select(CertificationSchedule)
            .where(
                CertificationSchedule.id == schedule_id,
                CertificationSchedule.session_id == session_id,
            )
            .options(selectinload(CertificationSchedule.certification))
        )
        if schedule is None:
            raise LookupError("Schedule not found")
        return schedule

    @staticmethod
    def _get_session(db: Session, session_id: int) -> CoachingSession:
        session = db.scalar(
            select(CoachingSession)
            .where(CoachingSession.id == session_id)
            .options(
                selectinload(CoachingSession.recommendations).selectinload(
                    CertificationRecommendation.certification
                ),
                selectinload(CoachingSession.messages),
                selectinload(CoachingSession.schedules).selectinload(CertificationSchedule.certification),
            )
        )
        if session is None:
            raise LookupError("Coaching session not found")
        return session
