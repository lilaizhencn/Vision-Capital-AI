from celery import Celery

from app.core.config import settings

settings.validate_production()

celery_app = Celery(
    "vision_capital_ai",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)
celery_app.conf.task_always_eager = settings.celery_task_always_eager
celery_app.conf.task_eager_propagates = True
celery_app.conf.task_acks_late = True
celery_app.conf.task_reject_on_worker_lost = True
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.beat_schedule = {
    "schedule-due-project-research": {
        "task": "schedule_due_project_research_task",
        "schedule": 600.0,
    },
    "recover-stale-document-parses": {
        "task": "recover_stale_parse_tasks_task",
        "schedule": 600.0,
    },
    "schedule-due-data-sources": {
        "task": "schedule_due_data_sources_task",
        "schedule": 600.0,
    },
}
