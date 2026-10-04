from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import get_db
from app.providers.groq_client import GroqClient, LLMError
from app.providers.groq_llm import GroqLLMProvider
from app.providers.mock_llm import MockLLMProvider
from app.providers.official_schedule import (
    MockOfficialScheduleAdapter,
    OfficialSiteScheduleProvider,
)
from app.providers.web_search import TavilySearchProvider
from app.schemas import (
    ChatMessageCreate,
    ChatReplyResponse,
    CoachInput,
    ConversationMessageResponse,
    CreateSessionResponse,
    DashboardResponse,
    MessageListResponse,
    RecommendationDetail,
    RecommendationListResponse,
    ScheduleListResponse,
    ScheduleResponse,
)
from app.security import (
    clear_session_rate_limit,
    create_session_token,
    enforce_rate_limit,
    hash_session_token,
    require_bff_secret,
    require_session_owner,
)
from app.services.chat import ChatNotConfiguredError, ChatService
from app.services.coaching import CATALOG, CoachingService

router = APIRouter(
    prefix="/api/v1",
    tags=["coaching"],
    dependencies=[Depends(require_bff_secret)],
)

# API key가 비어 있으면 Groq/Tavily 대신 mock 또는 검색 없이 동작한다
settings = get_settings()
groq_client = GroqClient(settings.groq_api_key, settings.groq_model) if settings.groq_api_key else None
search_provider = TavilySearchProvider(settings.tavily_api_key) if settings.tavily_api_key else None
llm_provider = (
    GroqLLMProvider(groq_client, CATALOG, fallback=MockLLMProvider(), search=search_provider)
    if groq_client
    else MockLLMProvider()
)

service = CoachingService(
    llm_provider=llm_provider,
    schedule_provider=OfficialSiteScheduleProvider(MockOfficialScheduleAdapter()),
)
chat_service = ChatService(groq_client, search_provider, settings.chat_history_limit)


def get_service() -> CoachingService:
    return service


def get_chat_service() -> ChatService:
    return chat_service


def not_found(error: LookupError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.post(
    "/coaching/sessions",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="추천 세션 생성",
)
def create_coaching_session(
    payload: CoachInput,
    request: Request,
    db: Session = Depends(get_db),
    coaching_service: CoachingService = Depends(get_service),
) -> CreateSessionResponse:
    settings = get_settings()
    enforce_rate_limit(
        db,
        scope="session-create",
        identity=request.headers.get("X-Rate-Limit-Key") or "",
        limit=settings.session_creation_limit_per_hour,
        window_seconds=settings.rate_limit_window_seconds,
        secret=settings.bff_shared_secret,
    )
    session_token = create_session_token()
    dashboard = coaching_service.create_session(
        db,
        session_token_hash=hash_session_token(session_token),
        **payload.model_dump(),
    )
    return CreateSessionResponse.model_validate(
        {**dashboard.model_dump(), "session_token": session_token}
    )


@router.get(
    "/coaching/sessions/{session_id}",
    response_model=DashboardResponse,
    summary="대시보드 통합 조회",
    dependencies=[Depends(require_session_owner)],
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
    dependencies=[Depends(require_session_owner)],
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
    dependencies=[Depends(require_session_owner)],
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
    dependencies=[Depends(require_session_owner)],
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
    dependencies=[Depends(require_session_owner)],
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
    dependencies=[Depends(require_session_owner)],
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
    dependencies=[Depends(require_session_owner)],
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


@router.post(
    "/coaching/sessions/{session_id}/messages",
    response_model=ChatReplyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="대화 이어가기 (요청 파악 → 검색 → 응답)",
    dependencies=[Depends(require_session_owner)],
)
def post_message(
    session_id: int,
    payload: ChatMessageCreate,
    db: Session = Depends(get_db),
    chat: ChatService = Depends(get_chat_service),
) -> ChatReplyResponse:
    settings = get_settings()
    enforce_rate_limit(
        db,
        scope="chat",
        identity=str(session_id),
        limit=settings.chat_messages_per_hour,
        window_seconds=settings.rate_limit_window_seconds,
        secret=settings.bff_shared_secret,
    )
    try:
        result = chat.reply(db, session_id, payload.message)
    except LookupError as error:
        raise not_found(error) from error
    except ChatNotConfiguredError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except LLMError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
    return ChatReplyResponse(
        session_id=session_id,
        intent=result.intent,
        user_message=result.user_message,
        assistant_message=result.assistant_message,
        notices=result.notices,
    )


@router.delete(
    "/coaching/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="현재 세션 삭제",
    dependencies=[Depends(require_session_owner)],
)
def delete_coaching_session(
    session_id: int,
    db: Session = Depends(get_db),
    coaching_service: CoachingService = Depends(get_service),
) -> Response:
    clear_session_rate_limit(db, session_id)
    try:
        coaching_service.delete_session(db, session_id)
    except LookupError as error:
        raise not_found(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
