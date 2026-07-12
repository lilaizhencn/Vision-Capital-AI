from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.project import Project
from app.models.file import ProjectFile
from app.models.research import EvidenceRequirement
from app.models.task import ProjectTask
from app.models.user import User
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate

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


@router.post("", response_model=TaskRead, status_code=201)
def create_task(
    project_id: str,
    payload: TaskCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _project(db, project_id, user)
    if payload.related_requirement_id and not db.scalar(select(EvidenceRequirement.id).where(
        EvidenceRequirement.id == payload.related_requirement_id,
        EvidenceRequirement.project_id == project_id,
    )):
        raise HTTPException(status_code=404, detail="Evidence requirement not found")
    values = payload.model_dump()
    file_ids = list(dict.fromkeys(values["evidence_file_ids"]))
    owned_count = len(list(db.scalars(select(ProjectFile.id).where(
        ProjectFile.project_id == project_id,
        ProjectFile.id.in_(file_ids),
    )))) if file_ids else 0
    if owned_count != len(file_ids):
        raise HTTPException(status_code=400, detail="Every evidence file must belong to this project")
    if payload.status == "completed" and not payload.result.strip() and not file_ids:
        raise HTTPException(status_code=400, detail="Add an execution result or evidence file before completing the task")
    values["evidence_file_ids"] = file_ids
    values["done"] = payload.status == "completed"
    values["completed_at"] = datetime.now(timezone.utc) if values["done"] else None
    task = ProjectTask(project_id=project_id, **values)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(project_id: str, task_id: str, payload: TaskUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _project(db, project_id, user)
    task = db.scalar(select(ProjectTask).where(ProjectTask.id == task_id, ProjectTask.project_id == project_id))
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    changes = payload.model_dump(exclude_unset=True)
    file_ids = changes.get("evidence_file_ids")
    if file_ids is not None:
        unique_ids = list(dict.fromkeys(file_ids))
        owned_count = len(list(db.scalars(select(ProjectFile.id).where(
            ProjectFile.project_id == project_id,
            ProjectFile.id.in_(unique_ids),
        )))) if unique_ids else 0
        if owned_count != len(unique_ids):
            raise HTTPException(status_code=400, detail="Every evidence file must belong to this project")
        changes["evidence_file_ids"] = unique_ids
    requirement_id = changes.get("related_requirement_id")
    if requirement_id and not db.scalar(select(EvidenceRequirement.id).where(
        EvidenceRequirement.id == requirement_id,
        EvidenceRequirement.project_id == project_id,
    )):
        raise HTTPException(status_code=400, detail="Evidence requirement must belong to this project")

    requested_status = changes.pop("status", None)
    requested_done = changes.pop("done", None)
    next_status = requested_status or ("completed" if requested_done is True else "todo" if requested_done is False else task.status)
    next_result = changes.get("result", task.result).strip()
    next_evidence = changes.get("evidence_file_ids", task.evidence_file_ids or [])
    if next_status == "completed" and not next_result and not next_evidence:
        raise HTTPException(status_code=400, detail="Add an execution result or evidence file before completing the task")
    for key, value in changes.items():
        setattr(task, key, value)
    task.status = next_status
    task.done = next_status == "completed"
    task.completed_at = datetime.now(timezone.utc) if task.done else None
    db.commit()
    db.refresh(task)
    return task
