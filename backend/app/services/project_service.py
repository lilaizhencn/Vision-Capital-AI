from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.task import ProjectTask
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.core.config import settings


class ProjectService:
    def __init__(self, db: Session):
        self.repo = ProjectRepository(db)

    def create(self, payload: ProjectCreate, user: User):
        project = self.repo.create(
            owner_id=user.id,
            next_research_at=datetime.now(timezone.utc) if payload.research_auto_enabled else None,
            **payload.model_dump(),
        )
        self.repo.db.add_all([
            ProjectTask(project_id=project.id, label="补充核心团队履历与分工"),
            ProjectTask(project_id=project.id, label="确认市场规模与竞争格局假设"),
            ProjectTask(project_id=project.id, label="复核最新一版财务预测", done=True),
        ])
        self.repo.db.commit()
        self.repo.db.refresh(project)
        if settings.research_auto_enrich_enabled and project.research_auto_enabled:
            self._queue_initial_research(project, user.id)
        return project

    def _queue_initial_research(self, project, owner_id: str) -> None:
        from app.workers.tasks import enrich_project_research_task

        project.research_status = "queued"
        self.repo.db.commit()
        try:
            enrich_project_research_task.delay(project.id, owner_id)
        except Exception as exc:
            project.research_status = "failed"
            project.research_last_error = f"Unable to queue automatic research: {exc}"[:2000]
            self.repo.db.commit()

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
