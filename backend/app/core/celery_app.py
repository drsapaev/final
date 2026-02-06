import os

from celery import Celery

from app.core.config import settings

celery_app = Celery("clinic", broker=settings.CELERY_BROKER_URL)

celery_app.conf.update(
    result_backend=settings.CELERY_RESULT_BACKEND,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.TIMEZONE,
    enable_utc=True,
    task_routes={
        "app.tasks.notifications.*": {"queue": "notifications"},
    },
)

# Load tasks
celery_app.autodiscover_tasks(["app.tasks.notifications"])
