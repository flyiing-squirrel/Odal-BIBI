import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import case, delete, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import get_db
from app.models import CoachingSession, RequestRateLimit

bearer_scheme = HTTPBearer(auto_error=False)
RATE_LIMIT_KEY_PATTERN = re.compile(r"^[a-f0-9]{64}$")


def create_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_session_token(token: str, stored_hash: str | None) -> bool:
    if stored_hash is None or len(token) > 128:
        return False
    return hmac.compare_digest(hash_session_token(token), stored_hash)


def require_bff_secret(
    x_bff_secret: Annotated[str | None, Header(alias="X-BFF-Secret")] = None,
) -> None:
    expected = get_settings().bff_shared_secret
    if len(expected.encode("utf-8")) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backend proxy is not configured",
        )
    if x_bff_secret is None or not hmac.compare_digest(x_bff_secret, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid proxy credentials",
        )


def require_session_owner(
    session_id: int,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    stored_hash = db.scalar(
        select(CoachingSession.session_token_hash).where(CoachingSession.id == session_id)
    )
    if not verify_session_token(credentials.credentials, stored_hash):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")


def rate_limit_key_hash(scope: str, identity: str, secret: str) -> str:
    message = f"{scope}:{identity}".encode()
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def enforce_rate_limit(
    db: Session,
    *,
    scope: str,
    identity: str,
    limit: int,
    window_seconds: int,
    secret: str,
) -> None:
    if limit < 1 or window_seconds < 1:
        raise RuntimeError("Rate limits must be positive")

    if scope == "session-create" and not RATE_LIMIT_KEY_PATTERN.fullmatch(identity):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client rate-limit identity is required",
        )

    now = datetime.now(UTC)
    window_epoch = int(now.timestamp()) // window_seconds * window_seconds
    window_start = datetime.fromtimestamp(window_epoch, UTC)
    key_hash = rate_limit_key_hash(scope, identity, secret)
    dialect = db.get_bind().dialect.name
    insert = postgresql_insert if dialect == "postgresql" else sqlite_insert if dialect == "sqlite" else None
    if insert is None:
        raise RuntimeError(f"Unsupported database dialect for rate limiting: {dialect}")

    statement = insert(RequestRateLimit).values(
        key_hash=key_hash,
        window_start=window_start,
        request_count=1,
    )
    same_window_count = case(
        (RequestRateLimit.window_start == window_start, RequestRateLimit.request_count + 1),
        else_=1,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[RequestRateLimit.key_hash],
        set_={"window_start": window_start, "request_count": same_window_count},
    ).returning(RequestRateLimit.request_count)

    try:
        request_count = db.execute(statement).scalar_one()
        db.commit()
    except Exception:
        db.rollback()
        raise

    if request_count > limit:
        retry_after = max(1, int((window_start + timedelta(seconds=window_seconds) - now).total_seconds()))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="요청이 많습니다. 잠시 후 다시 시도해 주세요.",
            headers={"Retry-After": str(retry_after)},
        )


def clear_session_rate_limit(db: Session, session_id: int) -> None:
    secret = get_settings().bff_shared_secret
    if secret:
        key_hash = rate_limit_key_hash("chat", str(session_id), secret)
        db.execute(delete(RequestRateLimit).where(RequestRateLimit.key_hash == key_hash))
