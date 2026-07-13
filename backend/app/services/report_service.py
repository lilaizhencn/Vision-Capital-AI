from fastapi import HTTPException, status
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.llm_service import LLMService
from app.models.project import Project
from app.repositories.file_repository import FileRepository
from app.repositories.report_repository import ReportRepository
from app.services.rag_service import RAGService
from app.services.ai_usage_service import AIUsageService
from app.services.research_service import ResearchService


class ReportService:
    def __init__(self, db: Session):
        self.db = db
        self.report_repo = ReportRepository(db)
        self.file_repo = FileRepository(db)
        self.rag_service = RAGService(db)
        self.llm_service = LLMService()

    def _ensure_project(self, project_id: str, owner_id: str) -> Project:
        project = self.db.scalar(select(Project).where(Project.id == project_id, Project.owner_id == owner_id))
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        return project

    def generate(self, project_id: str, owner_id: str):
        project = self._ensure_project(project_id, owner_id)
        AIUsageService(self.db).consume(owner_id, "report", f"report:{owner_id}:{uuid.uuid4()}")
        chunks = self.rag_service.investment_strategy_search(
            project_id,
            "investment report business revenue customers gross margin cash flow competition management regulation valuation risks pre-investment during-investment post-investment strategy",
            limit=18,
        )
        context_parts: list[str] = []
        for chunk in chunks:
            file = self.file_repo.get(chunk.file_id)
            source_label = file.filename if file else "Unknown"
            if file and file.source_url:
                source_label = f"{source_label} | official public source: {file.source_url}"
            context_parts.append(f"[{source_label}]\n{chunk.content}")
        requirements = ResearchService(self.db).requirements(project_id)
        gaps = [
            f"- {item.label}: {item.reason} Suggested document: {item.suggested_document}"
            for item in requirements if item.status.value != "covered"
        ]
        prompt = f"""
You are an institutional investment research copilot. Generate a Chinese investment committee research report.

Project: {project.company_name}; industry: {project.industry}; stage: {project.stage}.

Synthesize across all provided sources. Official filings and regulator/government publications may be treated as
primary public evidence; search snippets and unverified materials may not. Separate disclosed facts, cross-source
inference, and missing evidence. Add source filenames in parentheses after material claims.

Required Chinese sections:
1. Company overview
2. Evidence base and source quality
3. Business model and growth drivers
4. Industry, market, and competition
5. Management and governance
6. Financial and operating summary
7. Investment merits
8. Key risks and contradictory evidence
9. Due diligence questions
10. Pre-investment strategy
11. During-investment execution strategy
12. Post-investment monitoring strategy and KPIs
13. Missing or unverified evidence
14. Conditional conclusion

Rules:
- Never invent market size, CAGR, valuation, multiples, prices, management guidance, ratings, or recommendations.
- Put every missing value in the missing-evidence section with an owner/action for obtaining it.
- Do not propose numeric thresholds unless the evidence includes a baseline and rationale. Otherwise name the metric and assign collection/approval as a next action.
- For public companies, use watchlists, staged sizing, IC gates, risk limits, and hedge review, not private rights.
- Explicitly identify source conflicts and stale dates. The conclusion must be conditional, not buy/sell advice.

Automated evidence gaps:
{chr(10).join(gaps) or "No material automated coverage gap; human source verification remains required."}

Evidence:
{chr(10).join(context_parts)}
""".strip()
        content = self.llm_service.generate(prompt)
        review_prompt = f"""
Rewrite this Chinese investment report as a final evidence-controlled IC draft. Output only the revised report.
Remove every number, product name, competitor, customer claim, pipeline code, market claim, and financial trend that is
not explicitly present in the evidence. Derived arithmetic must show operands and be labeled analyst-derived. Do not
turn a disclosed risk into a claim that it occurred. Remove invented valuations, position sizes, stop losses, hedge
instruments, KPI thresholds, and market forecasts. Preserve actionable evidence requests and conditional conclusions.
Put unresolved claims in the missing-evidence section and cite source filenames beside material facts.

DRAFT:
{content}

EVIDENCE:
{chr(10).join(context_parts)}
""".strip()
        try:
            content = self.llm_service.generate(review_prompt)
        except RuntimeError:
            pass
        return self.report_repo.create(project_id=project_id, title="AI Investment Report", content=content)

    def list(self, project_id: str, owner_id: str):
        self._ensure_project(project_id, owner_id)
        return self.report_repo.list_for_project(project_id)

    def list_recent(self, owner_id: str):
        return self.report_repo.recent_for_owner(owner_id)
