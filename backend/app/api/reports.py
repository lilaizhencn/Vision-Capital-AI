from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.report import ReportRead
from app.services.report_service import ReportService

router = APIRouter(tags=["reports"])


@router.get("/api/reports", response_model=list[ReportRead])
def list_recent_reports(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ReportService(db).list_recent(user.id)


@router.post("/api/projects/{project_id}/reports/generate", response_model=ReportRead)
def generate_report(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ReportService(db).generate(project_id, user.id)


@router.get("/api/projects/{project_id}/reports", response_model=list[ReportRead])
def list_reports(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return ReportService(db).list(project_id, user.id)
