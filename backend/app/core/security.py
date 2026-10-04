import hashlib
import hmac
import secrets


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_value(value: str) -> str:
    """세션 토큰·클라이언트 IP는 원문 대신 해시만 저장한다."""
    return hashlib.sha256(value.encode()).hexdigest()


def token_matches(token: str, token_hash: str) -> bool:
    return hmac.compare_digest(hash_value(token), token_hash)
