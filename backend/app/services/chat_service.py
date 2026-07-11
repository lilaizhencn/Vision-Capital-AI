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

        is_strategy_question = self._is_strategy_question(message)
        chunks = (
            self.rag_service.investment_strategy_search(project_id=project_id, query=message)
            if is_strategy_question
            else self.rag_service.similarity_search(project_id=project_id, query=message)
        )
        citations: list[Citation] = []
        context_parts: list[str] = []

        for chunk in chunks:
            file = self.file_repo.get(chunk.file_id)
            filename = file.filename if file else "Unknown"
            citations.append(Citation(file_id=chunk.file_id, filename=filename, content=chunk.content[:400]))
            context_parts.append(f"[{filename}] {chunk.content}")

        prompt = (
            self._strategy_prompt(project, message, context_parts)
            if is_strategy_question
            else self._standard_prompt(message, context_parts)
        )

        self.chat_repo.create(project_id=project_id, role="user", content=message)
        answer = self.llm_service.generate(prompt)
        self.chat_repo.create(project_id=project_id, role="assistant", content=answer)
        return ChatResponse(answer=answer, citations=citations)

    @staticmethod
    def _is_strategy_question(message: str) -> bool:
        lowered = message.lower()
        return any(keyword in lowered for keyword in (
            "投前", "投中", "投后", "建仓", "仓位", "估值", "退出", "增持", "减持", "投委",
            "pre-investment", "post-investment", "strategy", "kpi",
        ))

    @staticmethod
    def _standard_prompt(message: str, context_parts: list[str]) -> str:
        return (
            "You are an institutional investment research assistant. Answer in the user's language. "
            "Use only the provided materials. If the materials are insufficient, state exactly what is missing.\n\n"
            f"User question:\n{message}\n\n"
            f"Materials:\n{'\n\n'.join(context_parts)}"
        )

    @staticmethod
    def _strategy_prompt(project, message: str, context_parts: list[str]) -> str:
        return f"""
You are a rigorous institutional investment research copilot. Answer in the user's language.

Project:
- Name: {project.name}
- Company: {project.company_name}
- Industry: {project.industry}
- Stage: {project.stage}
- Description: {project.description or "N/A"}

Rules:
1. Start with one concise recommendation: proceed, observe cautiously, or pause, and explain why.
2. Separate the answer into: Material facts, Strategy inference, and Missing or unverified information.
3. Do not present inferred actions or thresholds as disclosed facts.
4. If you propose a numeric threshold, label it as "recommended threshold, requires investment committee approval".
5. For "during-investment" or "投中" questions, interpret the phase as the investor's IC or transaction execution stage. Do not confuse it with the target company's own accounting for strategic investments unless the user explicitly asks about that.
6. Avoid legal, tax, or personalized financial advice. If valuation, share price, peer data, customer interviews, or management guidance are missing, say so.
7. Make the answer operational: actions, evidence to check, risks, triggers, and next steps.
8. Do not invent share prices, enterprise values, valuation multiples, management guidance, non-GAAP targets, or market data. If those data are not in the materials, put them under Missing or unverified information.
9. For a public company, do not recommend private-company instruments such as preferred shares, anti-dilution clauses, redemption rights, or investor control rights unless financing documents are provided. Use public-market execution controls such as watchlist, staged position sizing, IC gates, valuation range to be filled from market data, risk limits, and hedge review.
10. Use these headings when the user asks in Chinese: 建议, 资料事实, 策略推导, 待补充/待验证, 下一步动作.

User question:
{message}

Materials:
{'\n\n'.join(context_parts)}
""".strip()
