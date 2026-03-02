from celery import Celery
from app.config import settings

celery_app = Celery(
    "researcher",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.task_routes = {"worker.tasks.*": {"queue": "default"}}
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.task_acks_late = True
