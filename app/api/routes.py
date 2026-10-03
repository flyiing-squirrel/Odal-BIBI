from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.providers.mock_llm import MockLLMProvider
from app.providers.official_schedule import MockOfficialScheduleAdapter, OfficialSiteScheduleProvider
from app.schemas import (
    CoachInput,
    ConversationMessageResponse,
    DashboardResponse,
    MessageListResponse,
    RecommendationDetail,
    RecommendationListResponse,
    ScheduleListResponse,
    ScheduleResponse,
)
from app.services.coaching import CoachingService


router = APIRouter(prefix="/api/v1", tags=["coaching"])
service = CoachingService(
    llm_provider=MockLLMProvider(),
    schedule_provider=OfficialSiteScheduleProvider(MockOfficialScheduleAdapter()),
)


def get_service() -> CoachingService:
    return service


def not_found(error: LookupError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.post(
    "/coaching/sessions",
    response_model=DashboardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="추천 세션 생성",
)
def create_coaching_session(
    payload: CoachInput,
    db: Session = Depends(get_db),
    coaching_service: CoachingService = Depends(get_service),
) -> DashboardResponse:
    return coaching_service.create_session(db, **payload.model_dump())


@router.get(
    "/coaching/sessions/{session_id}",
    response_model=DashboardResponse,
    summary="대시보드 통합 조회",
)
def get_dashboard(
    session_id: int,
    db: Session = Depends(get_db),
    coaching_service: CoachingService = Depends(get_service),
) -> DashboardResponse:
    try:
        return coaching_service.get_dashboard(db, session_id)
    except LookupError as error:
        raise not_found(error) from error


@router.get(
    "/coaching/sessions/{session_id}/recommendations",
    response_model=RecommendationListResponse,
    summary="추천 자격증 목록",
)
def get_recommendations(
    session_id: int,
    db: Session = Depends(get_db),
    coaching_service: CoachingService = Depends(get_service),
) -> RecommendationListResponse:
    try:
        return RecommendationListResponse(
            session_id=session_id, items=coaching_service.get_recommendations(db, session_id)
        )
    except LookupError as error:
        raise not_found(error) from error


@router.get(
    "/coaching/sessions/{session_id}/recommendations/{recommendation_id}",
    response_model=RecommendationDetail,
    summary="추천 자격증 상세",
)
def get_recommendation(
    session_id: int,
    recommendation_id: int,
    db: Session = Depends(get_db),
    coaching_service: CoachingService = Depends(get_service),
) -> RecommendationDetail:
    try:
        return coaching_service.get_recommendation(db, session_id, recommendation_id)
    except LookupError as error:
        raise not_found(error) from error


@router.get(
    "/coaching/sessions/{session_id}/conversation",
    response_model=MessageListResponse,
    summary="대화 목록",
)
def get_conversation(
    session_id: int,
    db: Session = Depends(get_db),
    coaching_service: CoachingService = Depends(get_service),
) -> MessageListResponse:
    try:
        return MessageListResponse(
            session_id=session_id, items=coaching_service.get_messages(db, session_id)
        )
    except LookupError as error:
        raise not_found(error) from error


@router.get(
    "/coaching/sessions/{session_id}/conversation/{message_id}",
    response_model=ConversationMessageResponse,
    summary="대화 메시지 상세",
)
def get_conversation_message(
    session_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    coaching_service: CoachingService = Depends(get_service),
) -> ConversationMessageResponse:
    try:
        return coaching_service.get_message(db, session_id, message_id)
    except LookupError as error:
        raise not_found(error) from error


@router.get(
    "/coaching/sessions/{session_id}/schedules",
    response_model=ScheduleListResponse,
    summary="공식 자격증 일정 목록",
)
def get_schedules(
    session_id: int,
    db: Session = Depends(get_db),
    coaching_service: CoachingService = Depends(get_service),
) -> ScheduleListResponse:
    try:
        return ScheduleListResponse(
            session_id=session_id, items=coaching_service.get_schedules(db, session_id)
        )
    except LookupError as error:
        raise not_found(error) from error


@router.get(
    "/coaching/sessions/{session_id}/schedules/{schedule_id}",
    response_model=ScheduleResponse,
    summary="공식 자격증 일정 상세",
)
def get_schedule(
    session_id: int,
    schedule_id: int,
    db: Session = Depends(get_db),
    coaching_service: CoachingService = Depends(get_service),
) -> ScheduleResponse:
    try:
        return coaching_service.get_schedule(db, session_id, schedule_id)
    except LookupError as error:
        raise not_found(error) from error
