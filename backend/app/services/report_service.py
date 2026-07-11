from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.llm_service import LLMService
from app.models.project import Project
from app.repositories.report_repository import ReportRepository
from app.services.rag_service import RAGService


class ReportService:
    def __init__(self, db: Session):
        self.report_repo = ReportRepository(db)
        self.rag_service = RAGService(db)
        self.llm_service = LLMService()

    def _ensure_project(self, project_id: str, owner_id: str) -> None:
        project = self.report_repo.db.scalar(select(Project).where(Project.id == project_id, Project.owner_id == owner_id))
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    def generate(self, project_id: str, owner_id: str):
        self._ensure_project(project_id, owner_id)
        chunks = self.rag_service.investment_strategy_search(
            project_id,
            "investment report business revenue customers gross margin cash flow competition risks pre-investment during-investment post-investment strategy",
            limit=14,
        )
        context = "\n\n".join(chunk.content for chunk in chunks)
        prompt = f"""
You are an institutional investment research copilot. Generate the report in Chinese.

Use only the provided materials. Do not invent market size, CAGR, valuation multiples, share prices, management guidance, ratings, or buy/sell recommendations. If a value is missing, place it under "待补充/待验证".

Required sections:
1. 公司概览
2. 资料事实
3. 商业模式与增长驱动
4. 财务与经营摘要
5. 投资亮点
6. 主要风险
7. 尽调问题清单
8. 投前策略
9. 投中策略
10. 投后策略
11. 待补充/待验证
12. 条件式结论

Rules:
- Separate disclosed facts from strategy inference.
- If you propose a threshold, label it "建议阈值，需投资委员会确认".
- For public companies, use public-market execution controls such as watchlist, staged position sizing, IC gates, valuation range to be filled from market data, risk limits, and hedge review. Do not propose private financing rights unless the materials include financing documents.
- The conclusion must be conditional, not a final investment recommendation.

Materials:
{context}
"""
        content = self.llm_service.generate(prompt.strip())
        return self.report_repo.create(project_id=project_id, title="AI Investment Report", content=content)

    def list(self, project_id: str, owner_id: str):
        self._ensure_project(project_id, owner_id)
        return self.report_repo.list_for_project(project_id)

    def list_recent(self, owner_id: str):
        return self.report_repo.recent_for_owner(owner_id)
