from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.project import Project
from app.models.task import ProjectTask
from app.models.user import User
from app.schemas.task import TaskRead, TaskUpdate

router = APIRouter(prefix="/api/projects/{project_id}/tasks", tags=["tasks"])


def _project(db: Session, project_id: str, user: User) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id, Project.owner_id == user.id))
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.get("", response_model=list[TaskRead])
def list_tasks(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _project(db, project_id, user)
    return list(db.scalars(select(ProjectTask).where(ProjectTask.project_id == project_id).order_by(ProjectTask.created_at)))


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(project_id: str, task_id: str, payload: TaskUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _project(db, project_id, user)
    task = db.scalar(select(ProjectTask).where(ProjectTask.id == task_id, ProjectTask.project_id == project_id))
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    task.done = payload.done
    db.commit()
    db.refresh(task)
    return task
