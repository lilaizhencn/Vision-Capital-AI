from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.dashboard import router as dashboard_router
from app.api.files import router as files_router
from app.api.projects import router as projects_router
from app.api.reports import router as reports_router
from app.core.config import settings
from app.core.database import Base, engine
from app.models import *  # noqa: F401,F403

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(files_router)
app.include_router(chat_router)
app.include_router(reports_router)
app.include_router(dashboard_router)

