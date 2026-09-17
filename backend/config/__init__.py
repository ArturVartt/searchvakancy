# Гарантируем, что Celery app создаётся при старте Django,
# чтобы shared_task подхватывал наш app.
from .celery import app as celery_app

__all__ = ("celery_app",)
