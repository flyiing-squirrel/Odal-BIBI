import base64
import binascii
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import Settings
from app.models import (
    CalendarEventSync,
    CertificationSchedule,
    CoachingSession,
    GoogleCalendarConnection,
    GoogleOAuthState,
)
from app.providers.google_calendar import (
    CALENDAR_SCOPE,
    CalendarIntegrationError,
    CalendarReauthorizationRequired,
    GoogleCalendarProvider,
)
from app.security import verify_session_token

OAUTH_STATE_TTL = timedelta(minutes=10)


class CalendarNotConfiguredError(Exception):
    pass


class CalendarNotConnectedError(Exception):
    pass


class CalendarAlreadyConnectedError(Exception):
    pass


class CalendarScheduleNotVerifiedError(Exception):
    pass


class InvalidOAuthCallbackError(Exception):
    pass


def start_calendar_connection(db: Session, session_id: int, settings: Settings) -> str:
    if not settings.google_oauth_configured:
        raise CalendarNotConfiguredError
    if db.scalar(
        select(GoogleCalendarConnection.id).where(
            GoogleCalendarConnection.session_id == session_id
        )
    ):
        raise CalendarAlreadyConnectedError
    _encryption_key(settings.google_token_encryption_current_version, settings)
    provider = GoogleCalendarProvider(settings)
    state = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    db.execute(
        delete(GoogleOAuthState).where(
            (GoogleOAuthState.session_id == session_id)
            | (GoogleOAuthState.expires_at <= now)
        )
    )
    db.add(
        GoogleOAuthState(
            state_hash=hashlib.sha256(state.encode("utf-8")).hexdigest(),
            session_id=session_id,
            created_at=now,
            expires_at=now + OAUTH_STATE_TTL,
        )
    )
    try:
        authorization_url = provider.authorization_url(state)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return authorization_url


def consume_oauth_state(
    db: Session,
    *,
    state: str,
    bearer_token: str | None,
) -> int:
    if not bearer_token or len(bearer_token) > 128:
        raise InvalidOAuthCallbackError
    state_hash = hashlib.sha256(state.encode("utf-8")).hexdigest()
    now = datetime.now(UTC)
    row = db.scalar(
        select(GoogleOAuthState).where(
            GoogleOAuthState.state_hash == state_hash,
            GoogleOAuthState.expires_at > now,
        )
    )
    if row is None:
        raise InvalidOAuthCallbackError
    session = db.get(CoachingSession, row.session_id)
    if session is None or not verify_session_token(bearer_token, session.session_token_hash):
        raise InvalidOAuthCallbackError

    consumed_session_id = db.execute(
        delete(GoogleOAuthState)
        .where(
            GoogleOAuthState.state_hash == state_hash,
            GoogleOAuthState.session_id == row.session_id,
            GoogleOAuthState.expires_at > now,
        )
        .returning(GoogleOAuthState.session_id)
    ).scalar_one_or_none()
    if consumed_session_id is None:
        db.rollback()
        raise InvalidOAuthCallbackError
    db.commit()
    return consumed_session_id


def complete_calendar_connection(
    db: Session,
    *,
    session_id: int,
    code: str,
    settings: Settings,
) -> None:
    provider = GoogleCalendarProvider(settings)
    token = provider.exchange_code(code)
    existing = db.scalar(
        select(GoogleCalendarConnection).where(GoogleCalendarConnection.session_id == session_id)
    )
    calendar_id = existing.calendar_id if existing else None
    calendar_name = existing.calendar_name if existing else "Odal BIBI 자격증 일정"
    if not token.refresh_token and existing is None:
        raise CalendarIntegrationError("Google did not return a refresh token.")
    if calendar_id is None:
        calendar_id, calendar_name = provider.create_calendar(token.access_token)
    refresh_token = token.refresh_token
    if refresh_token is None and existing is not None:
        refresh_token = decrypt_refresh_token(existing.encrypted_refresh_token, session_id, settings)
    if refresh_token is None:
        raise CalendarIntegrationError("Google did not return a refresh token.")
    encrypted_token = encrypt_refresh_token(refresh_token, session_id, settings)
    if existing is None:
        existing = GoogleCalendarConnection(
            session_id=session_id,
            calendar_id=calendar_id,
            calendar_name=calendar_name,
            encrypted_refresh_token=encrypted_token,
            granted_scopes=" ".join(token.scopes or (CALENDAR_SCOPE,)),
            status="connected",
        )
        db.add(existing)
    else:
        existing.calendar_id = calendar_id
        existing.calendar_name = calendar_name
        existing.encrypted_refresh_token = encrypted_token
        existing.granted_scopes = " ".join(token.scopes or (CALENDAR_SCOPE,))
        existing.status = "connected"
    db.commit()


def calendar_status(db: Session, session_id: int) -> dict:
    connection = db.scalar(
        select(GoogleCalendarConnection).where(GoogleCalendarConnection.session_id == session_id)
    )
    if connection is None:
        return {"connected": False, "requires_reauthorization": False, "calendar_name": None}
    return {
        "connected": connection.status == "connected",
        "requires_reauthorization": connection.status == "reauthorization_required",
        "calendar_name": connection.calendar_name,
    }


def disconnect_calendar(db: Session, session_id: int, settings: Settings) -> bool:
    connection = db.scalar(
        select(GoogleCalendarConnection).where(GoogleCalendarConnection.session_id == session_id)
    )
    if connection is None:
        return False
    refresh_token = decrypt_refresh_token(connection.encrypted_refresh_token, session_id, settings)
    GoogleCalendarProvider(settings).revoke(refresh_token)
    db.execute(delete(CalendarEventSync).where(CalendarEventSync.session_id == session_id))
    db.delete(connection)
    db.commit()
    return True


def sync_verified_schedule(
    db: Session,
    *,
    session_id: int,
    schedule_id: int,
    settings: Settings,
) -> str:
    connection = db.scalar(
        select(GoogleCalendarConnection).where(
            GoogleCalendarConnection.session_id == session_id
        )
    )
    if connection is None or connection.status != "connected":
        raise CalendarNotConnectedError

    schedule = db.scalar(
        select(CertificationSchedule)
        .options(joinedload(CertificationSchedule.certification))
        .where(
            CertificationSchedule.id == schedule_id,
            CertificationSchedule.session_id == session_id,
        )
    )
    if schedule is None or not _schedule_source_is_verified(schedule):
        raise CalendarScheduleNotVerifiedError

    sync = db.scalar(
        select(CalendarEventSync).where(
            CalendarEventSync.session_id == session_id,
            CalendarEventSync.schedule_id == schedule_id,
        )
    )
    event_id = sync.google_event_id if sync else GoogleCalendarProvider.event_id(session_id, schedule_id)

    try:
        refresh_token = decrypt_refresh_token(connection.encrypted_refresh_token, session_id, settings)
        if connection.encrypted_refresh_token.split(".", 1)[0] != settings.google_token_encryption_current_version:
            connection.encrypted_refresh_token = encrypt_refresh_token(refresh_token, session_id, settings)
            db.flush()
        provider = GoogleCalendarProvider(settings)
        access_token = provider.refresh_access_token(refresh_token)
        event_id = provider.upsert_exam_event(
            access_token,
            connection.calendar_id,
            schedule,
            event_id,
            existing_event_id=sync.google_event_id if sync else None,
        )
    except CalendarReauthorizationRequired:
        connection.status = "reauthorization_required"
        db.commit()
        raise

    if sync is None:
        sync = CalendarEventSync(
            session_id=session_id,
            schedule_id=schedule_id,
            google_calendar_id=connection.calendar_id,
            google_event_id=event_id,
        )
        db.add(sync)
    else:
        sync.google_calendar_id = connection.calendar_id
        sync.google_event_id = event_id
        sync.synced_at = datetime.now(UTC)
    db.commit()
    return event_id


def encrypt_refresh_token(token: str, session_id: int, settings: Settings) -> str:
    version = settings.google_token_encryption_current_version
    key = _encryption_key(version, settings)
    nonce = secrets.token_bytes(12)
    aad = f"odal-google-refresh:{session_id}:{version}".encode()
    ciphertext = AESGCM(key).encrypt(nonce, token.encode("utf-8"), aad)
    encoded = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii").rstrip("=")
    return f"{version}.{encoded}"


def decrypt_refresh_token(value: str, session_id: int, settings: Settings) -> str:
    try:
        version, encoded = value.split(".", 1)
        payload = base64.b64decode(
            encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True
        )
        if len(payload) < 12 + 16:
            raise ValueError
        nonce, ciphertext = payload[:12], payload[12:]
        aad = f"odal-google-refresh:{session_id}:{version}".encode()
        plaintext = AESGCM(_encryption_key(version, settings)).decrypt(nonce, ciphertext, aad)
        return plaintext.decode("utf-8")
    except (ValueError, TypeError, binascii.Error, UnicodeDecodeError, InvalidTag):
        raise CalendarIntegrationError("Stored Google authorization data is unavailable.") from None


def _encryption_key(version: str, settings: Settings) -> bytes:
    if version not in {"v1", "v2"}:
        raise CalendarIntegrationError("Stored Google authorization data is unavailable.")
    encoded = getattr(settings, f"google_token_encryption_key_{version}", "")
    try:
        key = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
    except (ValueError, TypeError):
        key = b""
    if len(key) != 32:
        raise CalendarIntegrationError("Google token encryption is not configured.")
    return key


def _schedule_source_is_verified(schedule: CertificationSchedule) -> bool:
    if not schedule.source_verified:
        return False
    try:
        source = urlsplit(schedule.source_url)
        official = urlsplit(schedule.certification.official_url)
        source_host = source.hostname
        official_host = official.hostname
        source_port = source.port
        official_port = official.port
    except ValueError:
        return False
    if (
        source.scheme != "https"
        or official.scheme != "https"
        or not source_host
        or not official_host
        or source_port not in (None, 443)
        or official_port not in (None, 443)
        or source.username
        or source.password
        or official.username
        or official.password
    ):
        return False
    source_host = source_host.lower().rstrip(".")
    official_host = official_host.lower().rstrip(".")
    return source_host == official_host or source_host.endswith(f".{official_host}")
