from celery import Celery

celery_app = Celery(
    "q3_quant_engine",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
    include=["q3_quant_engine.tasks.strategy"],
)

celery_app.conf.task_routes = {
    "q3_quant_engine.tasks.strategy.run_strategy_task": {"queue": "strategy"},
    "q3_quant_engine.tasks.strategy.backtest_run_task": {"queue": "backtest"},
}
