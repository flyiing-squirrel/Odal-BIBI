from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import CoachingSession, ConversationMessage


class RateLimitError(RuntimeError):
    """LLM 호출이 일어나는 요청이 제한 횟수를 넘음."""


# 서버리스(Vercel)는 인스턴스가 여러 개라 메모리 카운터가 공유되지 않으므로 DB 기록으로 센다.
def _window_start(settings: Settings) -> datetime:
    return datetime.now(timezone.utc) - timedelta(minutes=settings.rate_limit_window_minutes)


def check_session_creation(db: Session, client_ip_hash: str, settings: Settings) -> None:
    count = db.scalar(
        select(func.count(CoachingSession.id)).where(
            CoachingSession.client_ip_hash == client_ip_hash,
            CoachingSession.created_at >= _window_start(settings),
        )
    )
    if count >= settings.max_sessions_per_window:
        raise RateLimitError(
            f"세션 생성은 {settings.rate_limit_window_minutes}분에 {settings.max_sessions_per_window}회까지 가능합니다."
        )


def check_message(db: Session, session_id: int, settings: Settings) -> None:
    # 세션 생성 시 저장되는 첫 메시지(사용자 프로필)는 대화 횟수에서 뺀다
    first_message_id = (
        select(func.min(ConversationMessage.id))
        .where(ConversationMessage.session_id == session_id)
        .scalar_subquery()
    )
    count = db.scalar(
        select(func.count(ConversationMessage.id)).where(
            ConversationMessage.session_id == session_id,
            ConversationMessage.role == "user",
            ConversationMessage.id > first_message_id,
            ConversationMessage.created_at >= _window_start(settings),
        )
    )
    if count >= settings.max_messages_per_window:
        raise RateLimitError(
            f"메시지는 {settings.rate_limit_window_minutes}분에 {settings.max_messages_per_window}회까지 보낼 수 있습니다."
        )
