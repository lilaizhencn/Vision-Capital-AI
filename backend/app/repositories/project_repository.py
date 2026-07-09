from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project


class ProjectRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **data) -> Project:
        project = Project(**data)
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def list_by_owner(self, owner_id: str) -> list[Project]:
        return list(self.db.scalars(select(Project).where(Project.owner_id == owner_id).order_by(Project.created_at.desc())))

    def get_for_owner(self, project_id: str, owner_id: str) -> Project | None:
        return self.db.scalar(select(Project).where(Project.id == project_id, Project.owner_id == owner_id))

    def delete(self, project: Project) -> None:
        self.db.delete(project)
        self.db.commit()

