"""
Celery application configuration for async task processing.
"""

import os
import sys
from celery import Celery

from app.core.config import settings

# Pre-load cuDNN DLL path for CUDA operations in worker (Windows only)
if sys.platform == "win32":
    _cudnn_bin = os.path.join(sys.prefix, "Lib", "site-packages", "nvidia", "cudnn", "bin")
    if os.path.isdir(_cudnn_bin):
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(_cudnn_bin)
        if _cudnn_bin not in os.environ.get("PATH", ""):
            os.environ["PATH"] = _cudnn_bin + os.pathsep + os.environ.get("PATH", "")

# Create data directories for filesystem broker (when Redis not available)
if not settings.celery_use_redis:
    os.makedirs("./data/celery-broker/out", exist_ok=True)
    os.makedirs("./data/celery-broker/processed", exist_ok=True)
    os.makedirs("./data/celery-results", exist_ok=True)

# Create Celery app
celery_app = Celery(
    "sales_pitch_analyzer",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.video_tasks",
        "app.tasks.analysis_tasks",
        "app.tasks.golden_pitch_tasks",
    ],
)

# Base configuration
config_updates = {
    # Task settings
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "UTC",
    "enable_utc": True,
    
    # Task execution settings
    "task_acks_late": True,
    "task_reject_on_worker_lost": True,
    "task_time_limit": 1800,  # 30 minutes hard limit
    "task_soft_time_limit": 1500,  # 25 minutes soft limit
    
    # Worker settings — sized for 50+ parallel RunPod polling tasks
    "worker_prefetch_multiplier": 4,
    "worker_concurrency": 20,
    
    # Result settings
    "result_expires": 86400,  # 24 hours
    
    # Task routes — separate RunPod polling into its own queue
    "task_routes": {
        "app.tasks.analysis_tasks.run_via_runpod_task": {"queue": "runpod"},
        "app.tasks.golden_pitch_tasks.*": {"queue": "default"},
    },
    
    # Task default queue
    "task_default_queue": "default",
    
    # Beat schedule (for periodic tasks if needed)
    "beat_schedule": {
        "cleanup-old-files": {
            "task": "app.tasks.video_tasks.cleanup_old_files",
            "schedule": 3600.0,  # Every hour
        },
    },
}

# Add filesystem broker config if not using Redis
if not settings.celery_use_redis:
    config_updates["broker_transport_options"] = {
        "data_folder_in": "./data/celery-broker/out",
        "data_folder_out": "./data/celery-broker/out",
        "data_folder_processed": "./data/celery-broker/processed",
    }

celery_app.conf.update(**config_updates)


from celery.signals import worker_init

@worker_init.connect
def _prewarm_models(**kwargs):
    """Pre-load heavy ML models when worker starts so first task is fast."""
    import logging
    log = logging.getLogger(__name__)
    try:
        from app.analyzers.transcription import WhisperTranscriber
        t = WhisperTranscriber()
        _ = t.model  # triggers singleton load
        log.info(f"Pre-warmed Whisper model on device={t.device}")
    except Exception as e:
        log.warning(f"Whisper pre-warm failed: {e}")


def get_celery_app() -> Celery:
    """Get the Celery application instance."""
    return celery_app
