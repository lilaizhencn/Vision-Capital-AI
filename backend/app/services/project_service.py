from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService:
    def __init__(self, db: Session):
        self.repo = ProjectRepository(db)

    def create(self, payload: ProjectCreate, user: User):
        return self.repo.create(owner_id=user.id, **payload.model_dump())

    def list(self, user: User):
        return self.repo.list_by_owner(user.id)

    def get(self, project_id: str, user: User):
        project = self.repo.get_for_owner(project_id, user.id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        return project

    def update(self, project_id: str, payload: ProjectUpdate, user: User):
        project = self.get(project_id, user)
        for key, value in payload.model_dump().items():
            setattr(project, key, value)
        self.repo.db.commit()
        self.repo.db.refresh(project)
        return project

    def delete(self, project_id: str, user: User):
        project = self.get(project_id, user)
        self.repo.delete(project)

