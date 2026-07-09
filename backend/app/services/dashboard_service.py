from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.file import ParseStatus, ProjectFile
from app.models.project import InvestmentStatus, Project
from app.repositories.report_repository import ReportRepository
from app.schemas.dashboard import DashboardSummary
from app.schemas.project import ProjectRead
from app.schemas.report import ReportRead


class DashboardService:
    def __init__(self, db: Session):
        self.db = db
        self.report_repo = ReportRepository(db)

    def summary(self, owner_id: str) -> DashboardSummary:
        total_projects = self.db.scalar(select(func.count(Project.id)).where(Project.owner_id == owner_id)) or 0
        pre_count = self.db.scalar(
            select(func.count(Project.id)).where(
                Project.owner_id == owner_id, Project.investment_status == InvestmentStatus.pre_investment
            )
        ) or 0
        in_progress = self.db.scalar(
            select(func.count(Project.id)).where(
                Project.owner_id == owner_id, Project.investment_status == InvestmentStatus.in_progress
            )
        ) or 0
        post_count = self.db.scalar(
            select(func.count(Project.id)).where(
                Project.owner_id == owner_id, Project.investment_status == InvestmentStatus.post_investment
            )
        ) or 0
        total_files = self.db.scalar(
            select(func.count(ProjectFile.id)).join(Project, ProjectFile.project_id == Project.id).where(Project.owner_id == owner_id)
        ) or 0
        completed_files = self.db.scalar(
            select(func.count(ProjectFile.id))
            .join(Project, ProjectFile.project_id == Project.id)
            .where(Project.owner_id == owner_id, ProjectFile.parse_status == ParseStatus.completed)
        ) or 0
        recent_projects = list(
            self.db.scalars(select(Project).where(Project.owner_id == owner_id).order_by(Project.created_at.desc()).limit(5))
        )
        return DashboardSummary(
            total_projects=total_projects,
            pre_investment_projects=pre_count,
            in_progress_projects=in_progress,
            post_investment_projects=post_count,
            total_files=total_files,
            completed_files=completed_files,
            recent_projects=[ProjectRead.model_validate(project) for project in recent_projects],
            recent_reports=[ReportRead.model_validate(report) for report in self.report_repo.recent()],
        )

