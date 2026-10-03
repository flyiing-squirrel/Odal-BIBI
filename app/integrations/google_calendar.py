import hashlib
from datetime import date, timedelta

from cryptography.fernet import Fernet, InvalidToken
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import get_settings

CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.app.created"
OAUTH_SCOPES = ["openid", "email", CALENDAR_SCOPE]
TOKEN_URI = "https://oauth2.googleapis.com/token"


def _client_config() -> dict[str, dict[str, object]]:
    settings = get_settings()
    return {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": TOKEN_URI,
            "redirect_uris": [settings.google_redirect_uri],
        }
    }


def make_oauth_flow(state: str | None = None) -> Flow:
    return Flow.from_client_config(
        _client_config(),
        scopes=OAUTH_SCOPES,
        state=state,
        redirect_uri=get_settings().google_redirect_uri,
    )


def verify_identity(token: str) -> dict[str, object]:
    claims = id_token.verify_oauth2_token(
        token, Request(), audience=get_settings().google_client_id
    )
    if claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        raise ValueError("Unexpected Google token issuer")
    if not claims.get("sub") or not claims.get("email") or not claims.get("email_verified"):
        raise ValueError("Google account identity is incomplete")
    return claims


def encrypt_refresh_token(token: str) -> str:
    key = get_settings().google_token_encryption_key
    if not key:
        raise RuntimeError("GOOGLE_TOKEN_ENCRYPTION_KEY is required")
    return Fernet(key.encode("ascii")).encrypt(token.encode("utf-8")).decode("ascii")


def decrypt_refresh_token(token: str) -> str:
    key = get_settings().google_token_encryption_key
    if not key:
        raise RuntimeError("GOOGLE_TOKEN_ENCRYPTION_KEY is required")
    try:
        return Fernet(key.encode("ascii")).decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as error:
        raise RuntimeError("Stored Google token could not be decrypted") from error


def credentials_for_refresh_token(refresh_token: str) -> Credentials:
    settings = get_settings()
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=OAUTH_SCOPES,
    )


def calendar_api(credentials: Credentials):
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def create_dedicated_calendar(credentials: Credentials) -> tuple[str, str]:
    calendar = (
        calendar_api(credentials)
        .calendars()
        .insert(
            body={
                "summary": "Odal BIBI",
                "description": "Odal BIBI에서 공식 출처가 확인된 자격증 시험일을 모아보는 캘린더입니다.",
            }
        )
        .execute()
    )
    return calendar["id"], calendar.get("summary", "Odal BIBI")


def upsert_exam_event(
    credentials: Credentials,
    *,
    user_id: int,
    schedule_id: int,
    calendar_id: str,
    certification_name: str,
    exam_name: str,
    exam_date: date,
    source_url: str,
) -> str:
    event_id = "od" + hashlib.sha256(f"{user_id}:{schedule_id}".encode()).hexdigest()[:48]
    body = {
        "id": event_id,
        "summary": f"{certification_name} · {exam_name}",
        "description": f"Odal BIBI에서 가져온 공식 시험 일정입니다.\n공식 출처: {source_url}",
        "start": {"date": exam_date.isoformat()},
        "end": {"date": (exam_date + timedelta(days=1)).isoformat()},
    }
    events = calendar_api(credentials).events()
    try:
        events.insert(calendarId=calendar_id, body=body).execute()
    except HttpError as error:
        if error.resp.status != 409:
            raise
        events.update(calendarId=calendar_id, eventId=event_id, body=body).execute()
    return event_id


def revoke_refresh_token(refresh_token: str) -> None:
    from httpx import post

    response = post(
        "https://oauth2.googleapis.com/revoke",
        data={"token": refresh_token},
        timeout=5,
    )
    if response.status_code not in {200, 400}:
        response.raise_for_status()
