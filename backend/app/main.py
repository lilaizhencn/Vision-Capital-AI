from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException
from sqlalchemy import text
from redis import Redis

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.dashboard import router as dashboard_router
from app.api.files import router as files_router
from app.api.projects import router as projects_router
from app.api.reports import router as reports_router
from app.api.monitoring import router as monitoring_router
from app.api.tasks import router as tasks_router
from app.api.websocket import router as websocket_router
from app.core.config import settings
from app.core.database import Base, engine
from app.models import *  # noqa: F401,F403

settings.validate_production()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/ready")
def readiness():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1).ping()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database or redis is unavailable") from exc
    return {"status": "ready"}


app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(files_router)
app.include_router(chat_router)
app.include_router(reports_router)
app.include_router(monitoring_router)
app.include_router(tasks_router)
app.include_router(dashboard_router)
app.include_router(websocket_router)
