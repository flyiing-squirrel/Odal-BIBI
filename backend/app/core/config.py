from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# .env는 저장소 루트에 하나만 둔다 (backend/에서 실행해도 루트 .env를 읽음).
# Docker·Vercel에서는 환경변수를 직접 주입하므로 이 파일이 없어도 된다.
ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
# DATABASE_URL을 비워 두면 backend/odal.db(SQLite)를 쓴다. Docker·Postgres 없이 바로 실행 가능.
DEFAULT_SQLITE_URL = f"sqlite:///{Path(__file__).resolve().parents[2] / 'odal.db'}"


class Settings(BaseSettings):
    app_name: str = "자격증 패스 코치 API"
    app_env: str = "local"
    database_url: str = DEFAULT_SQLITE_URL
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    tavily_api_key: str = ""
    bff_shared_secret: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""
    google_token_encryption_current_version: str = "v1"
    google_token_encryption_key_v1: str = ""
    google_token_encryption_key_v2: str = ""
    session_creation_limit_per_hour: int = Field(default=5, ge=1, le=100)
    profile_updates_per_hour: int = Field(default=5, ge=1, le=100)
    chat_messages_per_hour: int = Field(default=30, ge=1, le=1000)
    rate_limit_window_seconds: int = Field(default=3600, ge=60, le=86400)
    db_pool_size: int = Field(default=1, ge=1, le=10)
    db_max_overflow: int = Field(default=0, ge=0, le=10)
    db_pool_timeout: float = Field(default=5, gt=0, le=60)
    db_pool_pre_ping: bool = True
    # 대화 응답 생성 시 함께 넣을 이전 메시지 수
    chat_history_limit: int = 8
    # LLM 호출 비용 보호: 세션당 메시지 수, IP당 세션 생성 수 (rate_limit_window_minutes 기준)
    rate_limit_window_minutes: int = 10
    max_messages_per_window: int = 20
    max_sessions_per_window: int = 10

    model_config = SettingsConfigDict(env_file=ROOT_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str | None) -> str:
        # Neon·Vercel Postgres는 postgres:// 또는 postgresql:// 형태로 주므로 psycopg 드라이버를 지정한다
        if not value:
            return DEFAULT_SQLITE_URL
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def google_oauth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret and self.google_redirect_uri)


@lru_cache
def get_settings() -> Settings:
    return Settings()
