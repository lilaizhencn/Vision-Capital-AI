from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.project_service import ProjectService

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectRead)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ProjectService(db).create(payload, user)


@router.get("", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ProjectService(db).list(user)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ProjectService(db).get(project_id, user)


@router.put("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return ProjectService(db).update(project_id, payload, user)


@router.delete("/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ProjectService(db).delete(project_id, user)
    return {"message": "Project deleted"}

