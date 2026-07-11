from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.research import EnrichmentResponse, ResearchWorkspaceRead
from app.services.research_service import ResearchService
from app.workers.tasks import enrich_project_research_task

router = APIRouter(prefix="/api/projects/{project_id}/research", tags=["research"])


@router.get("", response_model=ResearchWorkspaceRead)
def get_research_workspace(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    requirements, sources = ResearchService(db).workspace(project_id, user.id)
    return ResearchWorkspaceRead(requirements=requirements, sources=sources)


@router.post("/enrich", response_model=EnrichmentResponse, status_code=202)
def enrich_project(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ResearchService(db)._project(project_id, user.id)
    result = enrich_project_research_task.delay(project_id, user.id)
    return EnrichmentResponse(status="queued", task_id=getattr(result, "id", None))
