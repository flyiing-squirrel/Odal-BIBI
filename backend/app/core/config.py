from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# .env는 저장소 루트에 하나만 둔다 (backend/에서 실행해도 루트 .env를 읽음).
# Docker에서는 compose가 환경변수를 주입하므로 이 파일이 없어도 된다.
ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    app_name: str = "자격증 패스 코치 API"
    app_env: str = "local"
    database_url: str = "postgresql+psycopg://odal:odal@localhost:5432/odal"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    tavily_api_key: str = ""
    bff_shared_secret: str = ""
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

    model_config = SettingsConfigDict(env_file=ROOT_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

