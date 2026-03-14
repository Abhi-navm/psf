"""Tasks module exports — guarded for environments without Celery."""

try:
    from app.tasks.celery_app import celery_app, get_celery_app
except ImportError:
    celery_app = None
    get_celery_app = None

__all__ = ["celery_app", "get_celery_app"]