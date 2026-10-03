from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "자격증 패스 코치 API"
    app_env: str = "local"
    database_url: str = "postgresql+psycopg://odal:odal@localhost:5432/odal"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    tavily_api_key: str = ""
    # 대화 응답 생성 시 함께 넣을 이전 메시지 수
    chat_history_limit: int = 8

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

