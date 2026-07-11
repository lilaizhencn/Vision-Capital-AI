from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.research import EnrichmentResponse, ResearchSettingsUpdate, ResearchWorkspaceRead
from app.services.research_service import ResearchService
from app.workers.tasks import enrich_project_research_task

router = APIRouter(prefix="/api/projects/{project_id}/research", tags=["research"])


@router.get("", response_model=ResearchWorkspaceRead)
def get_research_workspace(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service = ResearchService(db)
    project = service._project(project_id, user.id)
    requirements, sources = service.workspace(project_id, user.id)
    return ResearchWorkspaceRead(
        requirements=requirements,
        sources=sources,
        enrichment_running=project.research_status in {"queued", "running"},
        auto_enabled=project.research_auto_enabled,
        status=project.research_status,
        last_research_at=project.last_research_at,
        next_research_at=project.next_research_at,
        last_error=project.research_last_error,
    )


@router.post("/enrich", response_model=EnrichmentResponse, status_code=202)
def enrich_project(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = ResearchService(db)._project(project_id, user.id)
    if project.research_status in {"queued", "running"}:
        return EnrichmentResponse(status=project.research_status)
    project.research_status = "queued"
    project.research_last_error = None
    db.commit()
    try:
        result = enrich_project_research_task.delay(project_id, user.id)
    except Exception as exc:
        project.research_status = "failed"
        project.research_last_error = f"Unable to queue research: {exc}"[:2000]
        db.commit()
        raise
    return EnrichmentResponse(status="queued", task_id=getattr(result, "id", None))


@router.patch("/settings", response_model=ResearchWorkspaceRead)
def update_research_settings(
    project_id: str,
    payload: ResearchSettingsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service = ResearchService(db)
    project = service._project(project_id, user.id)
    project.research_auto_enabled = payload.auto_enabled
    if payload.auto_enabled and project.next_research_at is None:
        project.next_research_at = datetime.now(timezone.utc)
    db.commit()
    requirements, sources = service.workspace(project_id, user.id)
    return ResearchWorkspaceRead(
        requirements=requirements,
        sources=sources,
        enrichment_running=project.research_status in {"queued", "running"},
        auto_enabled=project.research_auto_enabled,
        status=project.research_status,
        last_research_at=project.last_research_at,
        next_research_at=project.next_research_at,
        last_error=project.research_last_error,
    )
