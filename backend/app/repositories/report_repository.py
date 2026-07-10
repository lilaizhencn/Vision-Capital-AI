from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.report import Report
from app.models.project import Project


class ReportRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **data) -> Report:
        report = Report(**data)
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def list_for_project(self, project_id: str) -> list[Report]:
        return list(self.db.scalars(select(Report).where(Report.project_id == project_id).order_by(Report.created_at.desc())))

    def recent(self, limit: int = 5) -> list[Report]:
        return list(self.db.scalars(select(Report).order_by(Report.created_at.desc()).limit(limit)))

    def recent_for_owner(self, owner_id: str, limit: int = 20) -> list[Report]:
        statement = (
            select(Report)
            .join(Project, Report.project_id == Project.id)
            .where(Project.owner_id == owner_id)
            .order_by(Report.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement))
