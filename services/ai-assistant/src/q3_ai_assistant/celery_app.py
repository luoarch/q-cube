from celery import Celery

from q3_ai_assistant.config import settings

celery_app = Celery(
    "q3_ai_assistant",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.task_routes = {
    "q3_ai_assistant.tasks.ai_tasks.explain_ranking": {"queue": "ai-ranking"},
    "q3_ai_assistant.tasks.ai_tasks.narrate_backtest": {"queue": "ai-backtest"},
    "q3_ai_assistant.tasks.ai_tasks.scan_for_pending": {"queue": "ai-ranking"},
    "q3_ai_assistant.tasks.retention.archive_old_sessions": {"queue": "ai-ranking"},
    "q3_ai_assistant.tasks.retention.expire_old_council_sessions": {"queue": "ai-ranking"},
}

celery_app.conf.beat_schedule = {
    "scan-for-pending": {
        "task": "q3_ai_assistant.tasks.ai_tasks.scan_for_pending",
        "schedule": settings.scan_interval_seconds,
    },
    "archive-old-sessions": {
        "task": "q3_ai_assistant.tasks.retention.archive_old_sessions",
        "schedule": 86400,  # daily
    },
    "expire-old-council-sessions": {
        "task": "q3_ai_assistant.tasks.retention.expire_old_council_sessions",
        "schedule": 86400,  # daily
    },
}
