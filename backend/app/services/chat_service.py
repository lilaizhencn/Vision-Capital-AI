from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.ai.llm_service import LLMService
from app.repositories.chat_repository import ChatRepository
from app.repositories.file_repository import FileRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.chat import Citation, ChatResponse
from app.services.rag_service import RAGService


class ChatService:
    def __init__(self, db: Session):
        self.db = db
        self.chat_repo = ChatRepository(db)
        self.file_repo = FileRepository(db)
        self.project_repo = ProjectRepository(db)
        self.rag_service = RAGService(db)
        self.llm_service = LLMService()

    def ask(self, project_id: str, message: str, user_id: str) -> ChatResponse:
        project = self.project_repo.get_for_owner(project_id, user_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        chunks = self.rag_service.similarity_search(project_id=project_id, query=message)
        citations: list[Citation] = []
        context_parts: list[str] = []

        for chunk in chunks:
            file = self.file_repo.get(chunk.file_id)
            filename = file.filename if file else "Unknown"
            citations.append(Citation(file_id=chunk.file_id, filename=filename, content=chunk.content[:400]))
            context_parts.append(f"[{filename}] {chunk.content}")

        prompt = (
            "你是一个企业级投资研究助理，请基于给定资料回答问题。\n"
            "如果资料不足，请明确说明缺失信息。\n\n"
            f"用户问题：{message}\n\n"
            f"资料上下文：\n{'\n\n'.join(context_parts)}"
        )

        self.chat_repo.create(project_id=project_id, role="user", content=message)
        answer = self.llm_service.generate(prompt)
        self.chat_repo.create(project_id=project_id, role="assistant", content=answer)
        return ChatResponse(answer=answer, citations=citations)
