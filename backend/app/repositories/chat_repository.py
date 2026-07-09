from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat import ChatMessage


class ChatRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **data) -> ChatMessage:
        message = ChatMessage(**data)
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def list_for_project(self, project_id: str) -> list[ChatMessage]:
        return list(
            self.db.scalars(select(ChatMessage).where(ChatMessage.project_id == project_id).order_by(ChatMessage.created_at))
        )

