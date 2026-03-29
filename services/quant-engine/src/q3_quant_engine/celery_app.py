from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    "q3_quant_engine",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
    include=[
        "q3_quant_engine.tasks.strategy",
        "q3_quant_engine.tasks.pilot_tasks",
    ],
)

celery_app.conf.task_routes = {
    "q3_quant_engine.tasks.strategy.run_strategy_task": {"queue": "strategy"},
    "q3_quant_engine.tasks.strategy.backtest_run_task": {"queue": "backtest"},
    "q3_quant_engine.tasks.pilot_tasks.take_daily_snapshot": {"queue": "strategy"},
    "q3_quant_engine.tasks.pilot_tasks.compute_all_forward_returns": {"queue": "strategy"},
}

# Pilot runtime schedule (MF-RUNTIME-01B)
# Snapshot: Mon-Fri 18:00 BRT (post-B3 close)
# Forward returns: Mon-Fri 19:00 BRT (1h after snapshot, prices updated)
celery_app.conf.beat_schedule = {
    "pilot-daily-snapshot": {
        "task": "q3_quant_engine.tasks.pilot_tasks.take_daily_snapshot",
        "schedule": crontab(hour=18, minute=0, day_of_week="1-5"),
    },
    "pilot-forward-returns": {
        "task": "q3_quant_engine.tasks.pilot_tasks.compute_all_forward_returns",
        "schedule": crontab(hour=19, minute=0, day_of_week="1-5"),
    },
    "b3-daily-fetch": {
        "task": "q3_quant_engine.tasks.pilot_tasks.fetch_b3_daily",
        "schedule": crontab(hour=20, minute=0, day_of_week="1-5"),
    },
    "refresh-compat-view": {
        "task": "q3_quant_engine.tasks.pilot_tasks.refresh_compat_view",
        "schedule": crontab(hour=20, minute=30, day_of_week="1-5"),
    },
}
