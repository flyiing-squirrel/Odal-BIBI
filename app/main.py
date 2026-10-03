from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.calendar import router as calendar_router
from app.api.routes import router, service
from app.core.config import get_settings
from app.db import SessionLocal


@asynccontextmanager
async def lifespan(_: FastAPI):
    with SessionLocal() as db:
        service.ensure_catalog(db)
    yield


settings = get_settings()
if settings.app_env != "local" and (
    len(settings.session_secret) < 32 or settings.session_secret == "local-only-change-before-deploy"
):
    raise RuntimeError("Set SESSION_SECRET to a random value of at least 32 characters")

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="자격증 추천·대화·공식 일정 데이터를 제공하는 대시보드용 REST API",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie="odal_session",
    max_age=14 * 24 * 60 * 60,
    same_site="lax" if settings.app_env == "local" else "none",
    https_only=settings.app_env != "local",
)
app.include_router(router)
app.include_router(calendar_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}

