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
