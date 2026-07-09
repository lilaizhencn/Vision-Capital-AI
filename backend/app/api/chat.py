from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(tags=["chat"])


@router.post("/api/projects/{project_id}/chat", response_model=ChatResponse)
def chat(
    project_id: str,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return ChatService(db).ask(project_id, payload.message, user.id)
