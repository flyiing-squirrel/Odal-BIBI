from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_value, token_matches
from app.db import get_db
from app.models import CoachingSession
from app.providers.groq_client import GroqClient, LLMError
from app.providers.groq_llm import GroqLLMProvider
from app.providers.mock_llm import MockLLMProvider
from app.providers.official_schedule import MockOfficialScheduleAdapter, OfficialSiteScheduleProvider
from app.providers.web_search import TavilySearchProvider
from app.schemas import (
    ChatMessageCreate,
    ChatReplyResponse,
    CoachInput,
    ConversationMessageResponse,
    DashboardResponse,
    MessageListResponse,
    RecommendationDetail,
    RecommendationListResponse,
    ScheduleListResponse,
    ScheduleResponse,
    SessionCreatedResponse,
)
from app.services import limits
from app.services.chat import ChatNotConfiguredError, ChatService
from app.services.coaching import CATALOG, CoachingService


router = APIRouter(prefix="/api/v1", tags=["coaching"])

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


def too_many_requests(error: limits.RateLimitError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(error))


def authorize_session(
    session_id: int,
    x_session_token: str | None = Header(default=None, description="세션 생성 응답의 access_token"),
    db: Session = Depends(get_db),
) -> None:
    """세션 소유자만 접근하게 한다. 토큰이 틀려도 404로 답해 다른 세션의 존재 여부를 숨긴다."""
    if not x_session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-Session-Token header required")
    token_hash = db.scalar(select(CoachingSession.access_token_hash).where(CoachingSession.id == session_id))
    if token_hash is None or not token_matches(x_session_token, token_hash):
        raise not_found(LookupError("Coaching session not found"))


def client_ip(request: Request) -> str:
    # Vercel은 x-forwarded-for 맨 앞에 실제 클라이언트 IP를 넣는다
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


@router.post(
    "/coaching/sessions",
    response_model=SessionCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="추천 세션 생성 (access_token 발급)",
)
def create_coaching_session(
    payload: CoachInput,
    request: Request,
    db: Session = Depends(get_db),
    coaching_service: CoachingService = Depends(get_service),
) -> SessionCreatedResponse:
    ip_hash = hash_value(client_ip(request))
    try:
        limits.check_session_creation(db, ip_hash, settings)
    except limits.RateLimitError as error:
        raise too_many_requests(error) from error
    return coaching_service.create_session(db, **payload.model_dump(), client_ip_hash=ip_hash)


@router.get(
    "/coaching/sessions/{session_id}",
    dependencies=[Depends(authorize_session)],
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
    dependencies=[Depends(authorize_session)],
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
    dependencies=[Depends(authorize_session)],
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
    dependencies=[Depends(authorize_session)],
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
    dependencies=[Depends(authorize_session)],
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
    dependencies=[Depends(authorize_session)],
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
    dependencies=[Depends(authorize_session)],
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


@router.post(
    "/coaching/sessions/{session_id}/messages",
    dependencies=[Depends(authorize_session)],
    response_model=ChatReplyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="대화 이어가기 (요청 파악 → 검색 → 응답)",
)
def post_message(
    session_id: int,
    payload: ChatMessageCreate,
    db: Session = Depends(get_db),
    chat: ChatService = Depends(get_chat_service),
) -> ChatReplyResponse:
    try:
        limits.check_message(db, session_id, settings)
        result = chat.reply(db, session_id, payload.message)
    except LookupError as error:
        raise not_found(error) from error
    except limits.RateLimitError as error:
        raise too_many_requests(error) from error
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
