from celery import Celery

from q3_fundamentals_engine.config import REDIS_URL

celery_app = Celery(
    "q3_fundamentals_engine",
    broker=f"{REDIS_URL}/0",
    backend=f"{REDIS_URL}/1",
    include=[
        "q3_fundamentals_engine.tasks.import_batch",
        "q3_fundamentals_engine.tasks.compute_metrics",
        "q3_fundamentals_engine.tasks.fetch_snapshots",
    ],
)

celery_app.conf.task_routes = {
    "q3_fundamentals_engine.tasks.*": {"queue": "fundamentals"},
}
