from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.monitoring import MonitoringUpdate
from app.models.project import Project
from app.models.user import User
from app.schemas.monitoring import MonitoringUpdateCreate, MonitoringUpdateRead

router = APIRouter(prefix="/api/projects/{project_id}/monitoring", tags=["monitoring"])


def _project(db: Session, project_id: str, user: User) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id, Project.owner_id == user.id))
    if not project:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.get("", response_model=list[MonitoringUpdateRead])
def list_monitoring(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _project(db, project_id, user)
    return list(db.scalars(select(MonitoringUpdate).where(MonitoringUpdate.project_id == project_id).order_by(MonitoringUpdate.created_at.desc())))


@router.post("", response_model=MonitoringUpdateRead)
def create_monitoring(project_id: str, payload: MonitoringUpdateCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _project(db, project_id, user)
    item = MonitoringUpdate(project_id=project_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
