from fastapi import APIRouter, Depends, status
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.lifecycle import DataSourceSubscription
from app.schemas.lifecycle import (
    DataSourceSubscriptionCreate,
    DataSourceSubscriptionRead,
    DataSourceSubscriptionUpdate,
    InvestmentOpinionRead,
    LifecycleSummary,
    MonitoringMetricCreate,
    MonitoringMetricRead,
    MonitoringObservationCreate,
    MonitoringObservationRead,
    RiskEventCreate,
    RiskEventRead,
    RiskEventUpdate,
    TransactionExecutionRead,
    TransactionExecutionWrite,
)
from app.services.lifecycle_service import LifecycleService

router = APIRouter(prefix="/api/projects/{project_id}/lifecycle", tags=["investment-lifecycle"])


@router.get("", response_model=LifecycleSummary)
def lifecycle_summary(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return LifecycleService(db).summary(project_id, user.id)


@router.put("/transaction", response_model=TransactionExecutionRead)
def upsert_transaction(
    project_id: str,
    payload: TransactionExecutionWrite,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return LifecycleService(db).upsert_transaction(project_id, user.id, payload)


@router.post("/metrics", response_model=MonitoringMetricRead, status_code=status.HTTP_201_CREATED)
def create_metric(
    project_id: str,
    payload: MonitoringMetricCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return LifecycleService(db).create_metric(project_id, user.id, payload)


@router.post("/metrics/{metric_id}/observations", response_model=MonitoringObservationRead, status_code=status.HTTP_201_CREATED)
def create_observation(
    project_id: str,
    metric_id: str,
    payload: MonitoringObservationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return LifecycleService(db).create_observation(project_id, metric_id, user.id, payload)


@router.post("/risks", response_model=RiskEventRead, status_code=status.HTTP_201_CREATED)
def create_risk(
    project_id: str,
    payload: RiskEventCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return LifecycleService(db).create_risk(project_id, user.id, payload)


@router.patch("/risks/{risk_id}", response_model=RiskEventRead)
def update_risk(
    project_id: str,
    risk_id: str,
    payload: RiskEventUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return LifecycleService(db).update_risk(project_id, risk_id, user.id, payload)


@router.get("/opinions", response_model=list[InvestmentOpinionRead])
def list_opinions(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return LifecycleService(db).opinions(project_id, user.id)


@router.post("/opinions/refresh", response_model=InvestmentOpinionRead)
def refresh_opinion(project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return LifecycleService(db).refresh_opinion(project_id, user.id)


@router.post("/data-sources", response_model=DataSourceSubscriptionRead, status_code=status.HTTP_201_CREATED)
def create_data_source(
    project_id: str,
    payload: DataSourceSubscriptionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return LifecycleService(db).create_data_source(project_id, user.id, payload)


@router.patch("/data-sources/{source_id}", response_model=DataSourceSubscriptionRead)
def update_data_source(
    project_id: str,
    source_id: str,
    payload: DataSourceSubscriptionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return LifecycleService(db).update_data_source(project_id, source_id, user.id, payload.model_dump(exclude_unset=True))


@router.post("/data-sources/{source_id}/run", status_code=status.HTTP_202_ACCEPTED)
def run_data_source(
    project_id: str,
    source_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service = LifecycleService(db)
    service.project(project_id, user.id)
    if not db.scalar(select(DataSourceSubscription.id).where(
        DataSourceSubscription.id == source_id,
        DataSourceSubscription.project_id == project_id,
    )):
        raise HTTPException(status_code=404, detail="Data source subscription not found")
    from app.workers.tasks import ingest_data_source_subscription_task
    result = ingest_data_source_subscription_task.delay(source_id, user.id)
    return {"status": "queued", "task_id": getattr(result, "id", None)}
