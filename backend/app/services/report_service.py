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
        chunks = self.rag_service.similarity_search(project_id, "请生成完整投资研究报告", limit=8)
        context = "\n\n".join(chunk.content for chunk in chunks)
        prompt = f"""
请根据以下项目资料生成投资研究报告，必须包含：
1. 公司概览
2. 行业分析
3. 商业模式
4. 团队与组织
5. 财务摘要
6. 投资亮点
7. 主要风险
8. 尽调问题清单
9. 投资建议
10. 投前 / 投中 / 投后关注点

项目资料：
{context}
"""
        content = self.llm_service.generate(prompt.strip())
        return self.report_repo.create(project_id=project_id, title="AI Investment Report", content=content)

    def list(self, project_id: str, owner_id: str):
        self._ensure_project(project_id, owner_id)
        return self.report_repo.list_for_project(project_id)
