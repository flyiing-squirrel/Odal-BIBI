from functools import lru_cache

from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "자격증 패스 코치 API"
    app_env: str = "local"
    database_url: str = "sqlite:///./coach.db"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    frontend_url: str = "http://localhost:3000"
    session_secret: str = "local-only-change-before-deploy"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/calendar/google/callback"
    google_token_encryption_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def google_oauth_configured(self) -> bool:
        if not all(
            [
                self.google_client_id,
                self.google_client_secret,
                self.google_redirect_uri,
                self.google_token_encryption_key,
            ]
        ):
            return False
        try:
            Fernet(self.google_token_encryption_key.encode("ascii"))
        except (UnicodeEncodeError, ValueError):
            return False
        return True


@lru_cache
def get_settings() -> Settings:
    return Settings()

