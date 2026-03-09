"""Poll Redis lists for queued jobs and dispatch Celery tasks.

The NestJS API pushes events to Redis lists (q3:strategy:jobs, q3:backtest:jobs).
This poller bridges them to Celery tasks that the worker can consume.
"""

from __future__ import annotations

import json
import logging
import threading
import time

import redis

from q3_quant_engine.celery_app import celery_app

logger = logging.getLogger(__name__)

STRATEGY_QUEUE = "q3:strategy:jobs"
BACKTEST_QUEUE = "q3:backtest:jobs"
POLL_INTERVAL = 1.0  # seconds


def _dispatch_strategy(event: dict) -> None:
    celery_app.send_task(
        "q3_quant_engine.tasks.strategy.run_strategy_task",
        args=[event["jobId"], event["runId"], event["tenantId"], event["strategy"]],
        queue="strategy",
    )
    logger.info("Dispatched strategy task run=%s", event["runId"])


def _dispatch_backtest(event: dict) -> None:
    celery_app.send_task(
        "q3_quant_engine.tasks.strategy.backtest_run_task",
        args=[event["jobId"], event["runId"], event["tenantId"], event["config"]],
        queue="backtest",
    )
    logger.info("Dispatched backtest task run=%s", event["runId"])


def _poll_loop(r: redis.Redis) -> None:  # type: ignore[type-arg]
    logger.info("Queue poller started (strategy=%s, backtest=%s)", STRATEGY_QUEUE, BACKTEST_QUEUE)
    while True:
        try:
            # Non-blocking pop from both queues
            for queue_key, dispatcher in [
                (STRATEGY_QUEUE, _dispatch_strategy),
                (BACKTEST_QUEUE, _dispatch_backtest),
            ]:
                raw = r.rpop(queue_key)
                if raw:
                    event = json.loads(raw)
                    dispatcher(event)
        except Exception:
            logger.exception("Queue poller error")
        time.sleep(POLL_INTERVAL)


def start_poller() -> threading.Thread:
    """Start the queue poller in a daemon thread."""
    r = redis.from_url("redis://localhost:6379/0")
    t = threading.Thread(target=_poll_loop, args=(r,), daemon=True, name="queue-poller")
    t.start()
    return t
