from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import get_db
from app.providers.evidence_verifier import GroqEvidenceVerifier
from app.providers.google_calendar import (
    CalendarIntegrationError,
    CalendarReauthorizationRequired,
)
from app.providers.groq_client import GroqClient, LLMError
from app.providers.groq_llm import GroqLLMProvider
from app.providers.mock_llm import MockLLMProvider
from app.providers.official_schedule import (
    OfficialSiteScheduleProvider,
    UnconfiguredOfficialScheduleAdapter,
)
from app.providers.web_search import TavilySearchProvider
from app.schemas import (
    BrowserChatMessageCreate,
    CalendarEventSyncResponse,
    ChatMessageCreate,
    ChatReplyResponse,
    CoachInput,
    ConversationMessageResponse,
    CreateSessionResponse,
    DashboardResponse,
    GoogleCalendarConnectResponse,
    GoogleCalendarStatusResponse,
    GoogleOAuthCallbackRequest,
    GoogleOAuthCallbackResponse,
    MessageListResponse,
    ProfileUpdate,
    RecommendationDetail,
    RecommendationListResponse,
    ScheduleListResponse,
    ScheduleResponse,
)
from app.security import (
    bearer_scheme,
    clear_session_rate_limit,
    create_session_token,
    enforce_rate_limit,
    hash_session_token,
    require_bff_secret,
    require_session_owner,
)
from app.services.calendar import (
    CalendarAlreadyConnectedError,
    CalendarNotConfiguredError,
    CalendarNotConnectedError,
    CalendarScheduleNotVerifiedError,
    InvalidOAuthCallbackError,
    calendar_status,
    complete_calendar_connection,
    consume_oauth_state,
    disconnect_calendar,
    start_calendar_connection,
    sync_verified_schedule,
)
from app.services.chat import ChatNotConfiguredError, ChatService
from app.services.coaching import CATALOG, CoachingService

router = APIRouter(
    prefix="/api/v1",
    tags=["coaching"],
    dependencies=[Depends(require_bff_secret)],
)

# 추천은 Groq 키가 없으면 기본 provider를 쓰고, 채팅은 키가 없으면 비활성화한다.
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
    schedule_provider=OfficialSiteScheduleProvider(UnconfiguredOfficialScheduleAdapter()),
)
chat_service = ChatService(
    groq_client,
    search_provider,
    settings.chat_history_limit,
    verifier=GroqEvidenceVerifier(groq_client) if groq_client else None,
)


def get_service() -> CoachingService:
    return service


def get_chat_service() -> ChatService:
    return chat_service


def not_found(error: LookupError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


def client_ip(request: Request) -> str:
    # Vercel은 x-forwarded-for 맨 앞에 실제 클라이언트 IP를 넣는다
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


@router.post(
    "/coaching/browser-session",
    response_model=DashboardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="브라우저 저장소용 추천 대시보드 생성",
)
def create_browser_session(
    payload: CoachInput,
    coaching_service: CoachingService = Depends(get_service),
) -> DashboardResponse:
    return coaching_service.create_browser_dashboard(payload.model_dump())


@router.post(
    "/coaching/browser-session/messages",
    response_model=ChatReplyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="브라우저 저장소용 대화 이어가기",
)
def post_browser_message(
    payload: BrowserChatMessageCreate,
    chat: ChatService = Depends(get_chat_service),
) -> ChatReplyResponse:
    try:
        result = chat.reply_browser(
            payload.profile.model_dump(),
            [item.model_dump() for item in payload.conversation],
            payload.message,
        )
    except ChatNotConfiguredError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except LLMError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
    return ChatReplyResponse(
        session_id=1,
        intent=result.intent,
        user_message=result.user_message,
        assistant_message=result.assistant_message,
        notices=result.notices,
    )


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


@router.patch(
    "/coaching/sessions/{session_id}/profile",
    response_model=DashboardResponse,
    summary="프로필 수정 후 추천 갱신",
    dependencies=[Depends(require_session_owner)],
)
def update_coaching_profile(
    session_id: int,
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    coaching_service: CoachingService = Depends(get_service),
) -> DashboardResponse:
    settings = get_settings()
    enforce_rate_limit(
        db,
        scope="profile-update",
        identity=str(session_id),
        limit=settings.profile_updates_per_hour,
        window_seconds=settings.rate_limit_window_seconds,
        secret=settings.bff_shared_secret,
    )
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="프로필 변경값이 없습니다.")
    if "interest_area" in changes and changes["interest_area"] is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="관심 분야는 비워둘 수 없습니다.",
        )
    try:
        return coaching_service.update_profile(db, session_id, changes)
    except LookupError as error:
        raise not_found(error) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error


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


@router.get(
    "/coaching/sessions/{session_id}/calendar",
    response_model=GoogleCalendarStatusResponse,
    summary="Google Calendar 연결 상태",
    dependencies=[Depends(require_session_owner)],
)
def get_google_calendar_status(
    session_id: int,
    db: Session = Depends(get_db),
) -> GoogleCalendarStatusResponse:
    return GoogleCalendarStatusResponse(**calendar_status(db, session_id))


@router.post(
    "/coaching/sessions/{session_id}/calendar/connect",
    response_model=GoogleCalendarConnectResponse,
    summary="Google Calendar 연결 시작",
    dependencies=[Depends(require_session_owner)],
)
def connect_google_calendar(
    session_id: int,
    db: Session = Depends(get_db),
) -> GoogleCalendarConnectResponse:
    try:
        return GoogleCalendarConnectResponse(
            authorization_url=start_calendar_connection(db, session_id, get_settings())
        )
    except CalendarNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Calendar is not configured",
        ) from error
    except CalendarAlreadyConnectedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Disconnect the current Google Calendar connection before connecting again",
        ) from error
    except CalendarIntegrationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Calendar is temporarily unavailable",
        ) from error


@router.post(
    "/coaching/sessions/{session_id}/calendar/schedules/{schedule_id}",
    response_model=CalendarEventSyncResponse,
    summary="확인된 시험 일정을 Google Calendar에 동기화",
    dependencies=[Depends(require_session_owner)],
)
def sync_google_calendar_schedule(
    session_id: int,
    schedule_id: int,
    db: Session = Depends(get_db),
) -> CalendarEventSyncResponse:
    try:
        event_id = sync_verified_schedule(
            db,
            session_id=session_id,
            schedule_id=schedule_id,
            settings=get_settings(),
        )
    except CalendarNotConnectedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Google Calendar is not connected",
        ) from error
    except CalendarScheduleNotVerifiedError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only verified official schedules can be synchronized",
        ) from error
    except CalendarReauthorizationRequired as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Reconnect Google Calendar to continue syncing",
        ) from error
    except CalendarIntegrationError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google Calendar could not complete the request",
        ) from error
    return CalendarEventSyncResponse(synced=True, event_id=event_id)


@router.delete(
    "/coaching/sessions/{session_id}/calendar",
    response_model=GoogleCalendarStatusResponse,
    summary="Google Calendar 연결 해제",
    dependencies=[Depends(require_session_owner)],
)
def disconnect_google_calendar(
    session_id: int,
    db: Session = Depends(get_db),
) -> GoogleCalendarStatusResponse:
    try:
        disconnect_calendar(db, session_id, get_settings())
    except CalendarIntegrationError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google authorization could not be revoked; the connection was retained",
        ) from error
    return GoogleCalendarStatusResponse(**calendar_status(db, session_id))


@router.post(
    "/calendar/callback",
    response_model=GoogleOAuthCallbackResponse,
    summary="Google Calendar OAuth callback",
)
def google_calendar_callback(
    payload: GoogleOAuthCallbackRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> GoogleOAuthCallbackResponse:
    try:
        session_id = consume_oauth_state(
            db,
            state=payload.state,
            bearer_token=credentials.credentials if credentials else None,
        )
    except InvalidOAuthCallbackError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google Calendar authorization could not be verified",
        ) from error

    if payload.error is not None:
        return GoogleOAuthCallbackResponse(status="cancelled")
    try:
        complete_calendar_connection(
            db, session_id=session_id, code=payload.code or "", settings=get_settings()
        )
    except CalendarIntegrationError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google Calendar connection could not be completed",
        ) from error
    except (SQLAlchemyError, ValueError):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google Calendar connection could not be completed",
        ) from None
    return GoogleOAuthCallbackResponse(status="connected")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
