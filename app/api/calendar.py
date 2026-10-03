import secrets
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from google.auth.exceptions import GoogleAuthError, RefreshError
from googleapiclient.errors import HttpError
from httpx import HTTPError
from oauthlib.oauth2 import OAuth2Error
from pydantic import BaseModel
from requests import RequestException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import get_current_user, get_optional_user, require_same_origin
from app.core.config import get_settings
from app.db import get_db
from app.integrations.google_calendar import (
    create_dedicated_calendar,
    credentials_for_refresh_token,
    decrypt_refresh_token,
    encrypt_refresh_token,
    make_oauth_flow,
    revoke_refresh_token,
    upsert_exam_event,
    verify_identity,
)
from app.models import (
    CalendarEventSync,
    CertificationSchedule,
    CoachingSession,
    GoogleCalendarConnection,
    User,
)

router = APIRouter(prefix="/api/v1/calendar/google", tags=["google-calendar"])
OAUTH_STATE_MAX_AGE_SECONDS = 600


class ConnectionStatus(BaseModel):
    configured: bool
    connected: bool
    status: str
    email: str | None = None
    calendar_name: str | None = None


class SyncResponse(BaseModel):
    schedule_id: int
    calendar_name: str
    synced: bool = True


def frontend_redirect(result: str) -> RedirectResponse:
    return RedirectResponse(
        f"{get_settings().frontend_url.rstrip('/')}/?section=schedule&calendar={result}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/connect", include_in_schema=False)
def start_connection(request: Request) -> RedirectResponse:
    settings = get_settings()
    if not settings.google_oauth_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth client and token encryption key are not configured",
        )
    state = secrets.token_urlsafe(32)
    request.session["calendar_oauth_state"] = state
    request.session["calendar_oauth_started_at"] = int(time.time())
    current_user_id = request.session.get("user_id")
    request.session["calendar_oauth_user_id"] = (
        current_user_id if isinstance(current_user_id, int) else None
    )
    authorization_url, _ = make_oauth_flow(state).authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return RedirectResponse(authorization_url, status_code=status.HTTP_302_FOUND)


@router.get("/callback", include_in_schema=False)
def finish_connection(
    request: Request,
    state: str | None = None,
    code: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    expected_state = request.session.pop("calendar_oauth_state", None)
    started_at = request.session.pop("calendar_oauth_started_at", None)
    initiating_user_id = request.session.pop("calendar_oauth_user_id", None)
    if (
        not isinstance(expected_state, str)
        or not isinstance(state, str)
        or not secrets.compare_digest(expected_state, state)
        or not isinstance(started_at, int)
        or time.time() - started_at > OAUTH_STATE_MAX_AGE_SECONDS
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )
    if error or not code:
        return frontend_redirect("cancelled")

    try:
        flow = make_oauth_flow(state)
        flow.fetch_token(code=code)
        credentials = flow.credentials
        claims = verify_identity(credentials.id_token)
    except (GoogleAuthError, OAuth2Error, RequestException, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google authorization could not be verified",
        ) from None

    google_sub = str(claims["sub"])
    email = str(claims["email"])
    user = db.scalar(select(User).where(User.google_sub == google_sub))
    if isinstance(initiating_user_id, int):
        initiating_user = db.get(User, initiating_user_id)
        if initiating_user is not None and initiating_user.google_sub != google_sub:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Reconnect with the Google account already used by this profile",
            )
    if user is None:
        user = User(google_sub=google_sub, email=email)
        db.add(user)
        db.flush()
    else:
        user.email = email

    connection = db.scalar(
        select(GoogleCalendarConnection).where(GoogleCalendarConnection.user_id == user.id)
    )
    if connection is None:
        connection = GoogleCalendarConnection(user_id=user.id)
        db.add(connection)
    if credentials.refresh_token:
        try:
            connection.refresh_token_encrypted = encrypt_refresh_token(credentials.refresh_token)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google token encryption is not configured correctly",
            ) from None
    elif connection.status in {"disconnected", "reauthorization_required"}:
        connection.refresh_token_encrypted = None
    connection.granted_scopes = " ".join(credentials.scopes or [])
    connection.updated_at = datetime.now(UTC)
    if not connection.refresh_token_encrypted:
        connection.status = "reauthorization_required"
        db.commit()
        request.session["user_id"] = user.id
        return frontend_redirect("reauthorize")

    connection.status = "connected" if connection.calendar_id else "setup_required"
    db.commit()
    request.session["user_id"] = user.id

    if not connection.calendar_id:
        try:
            calendar_id, calendar_summary = create_dedicated_calendar(credentials)
        except (GoogleAuthError, HttpError, RequestException, KeyError, ValueError):
            connection.status = "setup_required"
            db.commit()
            return frontend_redirect("setup_error")
        connection.calendar_id = calendar_id
        connection.calendar_summary = calendar_summary
        connection.status = "connected"
        connection.updated_at = datetime.now(UTC)
        db.commit()
    return frontend_redirect("connected")


@router.get("/connection", response_model=ConnectionStatus)
def get_connection(
    response: Response,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> ConnectionStatus:
    response.headers["Cache-Control"] = "no-store"
    settings = get_settings()
    if user is None:
        return ConnectionStatus(
            configured=settings.google_oauth_configured,
            connected=False,
            status="disconnected",
        )
    connection = db.scalar(
        select(GoogleCalendarConnection).where(GoogleCalendarConnection.user_id == user.id)
    )
    if connection is None:
        return ConnectionStatus(
            configured=settings.google_oauth_configured,
            connected=False,
            status="disconnected",
        )
    connected = connection.status == "connected" and bool(connection.calendar_id)
    return ConnectionStatus(
        configured=settings.google_oauth_configured,
        connected=connected,
        status=connection.status,
        email=user.email,
        calendar_name=connection.calendar_summary if connected else None,
    )


@router.delete("/connection", response_model=ConnectionStatus)
def disconnect(
    user: User = Depends(get_current_user),
    _: None = Depends(require_same_origin),
    db: Session = Depends(get_db),
) -> ConnectionStatus:
    connection = db.scalar(
        select(GoogleCalendarConnection).where(GoogleCalendarConnection.user_id == user.id)
    )
    if connection is not None:
        if connection.refresh_token_encrypted:
            try:
                revoke_refresh_token(decrypt_refresh_token(connection.refresh_token_encrypted))
            except (HTTPError, RuntimeError):
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Google could not revoke the connection; try again",
                ) from None
        connection.refresh_token_encrypted = None
        connection.granted_scopes = ""
        connection.status = "disconnected"
        connection.updated_at = datetime.now(UTC)
        db.commit()
    return ConnectionStatus(
        configured=get_settings().google_oauth_configured,
        connected=False,
        status="disconnected",
    )


@router.post("/schedules/{schedule_id}", response_model=SyncResponse)
def sync_schedule(
    schedule_id: int,
    user: User = Depends(get_current_user),
    _: None = Depends(require_same_origin),
    db: Session = Depends(get_db),
) -> SyncResponse:
    schedule = db.scalar(
        select(CertificationSchedule)
        .join(CoachingSession, CoachingSession.id == CertificationSchedule.session_id)
        .where(CertificationSchedule.id == schedule_id, CoachingSession.user_id == user.id)
        .options(joinedload(CertificationSchedule.certification))
    )
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    if (
        not schedule.source_verified
        or "mock" in schedule.source_name.casefold()
        or not schedule.source_url.startswith("https://")
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only schedules verified against an official source can be added",
        )

    connection = db.scalar(
        select(GoogleCalendarConnection).where(GoogleCalendarConnection.user_id == user.id)
    )
    if (
        connection is None
        or connection.status != "connected"
        or not connection.calendar_id
        or not connection.refresh_token_encrypted
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Connect Google Calendar before adding an exam date",
        )
    try:
        refresh_token = decrypt_refresh_token(connection.refresh_token_encrypted)
        credentials = credentials_for_refresh_token(refresh_token)
        event_id = upsert_exam_event(
            credentials,
            user_id=user.id,
            schedule_id=schedule.id,
            calendar_id=connection.calendar_id,
            certification_name=schedule.certification.name,
            exam_name=schedule.exam_name,
            exam_date=schedule.exam_date,
            source_url=schedule.source_url,
        )
    except RefreshError:
        connection.status = "reauthorization_required"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Reconnect Google Calendar to continue",
        ) from None
    except HttpError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google Calendar could not save this exam date",
        ) from None
    except (GoogleAuthError, RequestException, RuntimeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google Calendar sync failed",
        ) from None

    sync = db.scalar(
        select(CalendarEventSync).where(
            CalendarEventSync.user_id == user.id,
            CalendarEventSync.schedule_id == schedule.id,
        )
    )
    if sync is None:
        sync = CalendarEventSync(
            user_id=user.id,
            schedule_id=schedule.id,
            calendar_id=connection.calendar_id,
            google_event_id=event_id,
        )
        db.add(sync)
    sync.calendar_id = connection.calendar_id
    sync.google_event_id = event_id
    sync.synced_at = datetime.now(UTC)
    db.commit()
    return SyncResponse(schedule_id=schedule.id, calendar_name=connection.calendar_summary)
