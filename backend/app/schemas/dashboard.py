from pydantic import BaseModel

from app.schemas.project import ProjectRead
from app.schemas.report import ReportRead


class DashboardSummary(BaseModel):
    total_projects: int
    pre_investment_projects: int
    in_progress_projects: int
    post_investment_projects: int
    total_files: int
    completed_files: int
    recent_projects: list[ProjectRead]
    recent_reports: list[ReportRead]

