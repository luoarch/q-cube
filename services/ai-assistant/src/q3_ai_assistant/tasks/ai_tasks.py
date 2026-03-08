from __future__ import annotations

import logging
import uuid
from datetime import date

import redis as redis_lib
from sqlalchemy import select

from q3_ai_assistant.celery_app import celery_app
from q3_ai_assistant.config import settings
from q3_ai_assistant.db.session import SessionLocal
from q3_ai_assistant.llm.cache import LLMCache
from q3_ai_assistant.llm.factory import create_adapter
from q3_ai_assistant.models.entities import AIModule, AISuggestion
from q3_ai_assistant.modules.backtest_narrator import narrate_backtest
from q3_ai_assistant.modules.ranking_explainer import explain_ranking

logger = logging.getLogger(__name__)

_redis: redis_lib.Redis | None = None


def _get_redis() -> redis_lib.Redis:
    global _redis
    if _redis is None:
        _redis = redis_lib.from_url(settings.redis_url, decode_responses=True)
    return _redis


def _check_daily_cost_cap() -> bool:
    r = _get_redis()
    today = date.today().isoformat()
    key = f"ai:cost:daily:{today}"
    current = float(r.get(key) or 0)
    if current >= settings.cost_limit_usd_daily:
        logger.warning("daily cost cap reached: $%.2f / $%.2f", current, settings.cost_limit_usd_daily)
        return False
    return True


def _increment_daily_cost(cost_usd: float) -> None:
    r = _get_redis()
    today = date.today().isoformat()
    key = f"ai:cost:daily:{today}"
    pipe = r.pipeline()
    pipe.incrbyfloat(key, cost_usd)
    pipe.expire(key, 172800)  # 48h TTL
    pipe.execute()


@celery_app.task(name="q3_ai_assistant.tasks.ai_tasks.scan_for_pending")
def scan_for_pending() -> dict:
    if not settings.enabled:
        return {"status": "disabled"}

    if not _check_daily_cost_cap():
        return {"status": "cost_cap_reached"}

    enqueued = {"ranking": 0, "backtest": 0}

    with SessionLocal() as session:
        # Import shared models to query strategy_runs and backtest_runs
        from q3_shared_models.entities import BacktestRun, RunStatus, StrategyRun

        # Find completed strategy runs without AI explanations
        existing_ranking = select(AISuggestion.trigger_entity_id).where(
            AISuggestion.module == AIModule.ranking_explainer
        ).scalar_subquery()

        strategy_candidates = session.execute(
            select(StrategyRun.id, StrategyRun.tenant_id).where(
                StrategyRun.status == RunStatus.completed,
                StrategyRun.result_json.isnot(None),
                StrategyRun.id.notin_(existing_ranking),
            ).limit(10)
        ).all()

        r = _get_redis()
        for run_id, tenant_id in strategy_candidates:
            lock_key = f"ai:claim:ranking_explainer:{run_id}"
            if r.set(lock_key, "1", nx=True, ex=300):
                explain_ranking_task.delay(str(run_id), str(tenant_id))
                enqueued["ranking"] += 1

        # Find completed backtest runs without AI narratives
        existing_backtest = select(AISuggestion.trigger_entity_id).where(
            AISuggestion.module == AIModule.backtest_narrator
        ).scalar_subquery()

        backtest_candidates = session.execute(
            select(BacktestRun.id, BacktestRun.tenant_id).where(
                BacktestRun.status == RunStatus.completed,
                BacktestRun.metrics_json.isnot(None),
                BacktestRun.id.notin_(existing_backtest),
            ).limit(10)
        ).all()

        for run_id, tenant_id in backtest_candidates:
            lock_key = f"ai:claim:backtest_narrator:{run_id}"
            if r.set(lock_key, "1", nx=True, ex=300):
                narrate_backtest_task.delay(str(run_id), str(tenant_id))
                enqueued["backtest"] += 1

    if enqueued["ranking"] or enqueued["backtest"]:
        logger.info("scan_for_pending enqueued: %s", enqueued)

    return {"status": "ok", "enqueued": enqueued}


@celery_app.task(name="q3_ai_assistant.tasks.ai_tasks.explain_ranking")
def explain_ranking_task(run_id: str, tenant_id: str) -> dict:
    parsed_run_id = uuid.UUID(run_id)
    parsed_tenant_id = uuid.UUID(tenant_id)
    r = _get_redis()
    lock_key = f"ai:claim:ranking_explainer:{run_id}"

    try:
        with SessionLocal() as session:
            from q3_shared_models.entities import StrategyRun

            strategy_run = session.execute(
                select(StrategyRun).where(StrategyRun.id == parsed_run_id)
            ).scalar_one()

            ranked_assets = (strategy_run.result_json or {}).get("rankedAssets", [])
            if not ranked_assets:
                logger.warning("strategy run %s has no rankedAssets", run_id)
                return {"status": "skipped", "reason": "no_ranked_assets"}

            adapter = create_adapter(settings)
            cache = LLMCache(r, ttl_seconds=settings.cache_ttl_seconds)

            suggestion = explain_ranking(
                session,
                adapter,
                cache,
                tenant_id=parsed_tenant_id,
                strategy_run_id=parsed_run_id,
                ranked_assets=ranked_assets,
            )

            session.commit()
            _increment_daily_cost(suggestion.cost_usd)

            logger.info("explain_ranking completed run=%s suggestion=%s", run_id, suggestion.id)
            return {"status": "completed", "suggestion_id": str(suggestion.id)}

    except Exception:
        logger.exception("explain_ranking failed run=%s", run_id)
        return {"status": "failed", "run_id": run_id}
    finally:
        r.delete(lock_key)


@celery_app.task(name="q3_ai_assistant.tasks.ai_tasks.narrate_backtest")
def narrate_backtest_task(run_id: str, tenant_id: str) -> dict:
    parsed_run_id = uuid.UUID(run_id)
    parsed_tenant_id = uuid.UUID(tenant_id)
    r = _get_redis()
    lock_key = f"ai:claim:backtest_narrator:{run_id}"

    try:
        with SessionLocal() as session:
            from q3_shared_models.entities import BacktestRun

            backtest_run = session.execute(
                select(BacktestRun).where(BacktestRun.id == parsed_run_id)
            ).scalar_one()

            metrics = backtest_run.metrics_json or {}
            config = backtest_run.config_json or {}

            if not metrics:
                logger.warning("backtest run %s has no metrics", run_id)
                return {"status": "skipped", "reason": "no_metrics"}

            adapter = create_adapter(settings)
            cache = LLMCache(r, ttl_seconds=settings.cache_ttl_seconds)

            suggestion = narrate_backtest(
                session,
                adapter,
                cache,
                tenant_id=parsed_tenant_id,
                backtest_run_id=parsed_run_id,
                metrics=metrics,
                config=config,
            )

            session.commit()
            _increment_daily_cost(suggestion.cost_usd)

            logger.info("narrate_backtest completed run=%s suggestion=%s", run_id, suggestion.id)
            return {"status": "completed", "suggestion_id": str(suggestion.id)}

    except Exception:
        logger.exception("narrate_backtest failed run=%s", run_id)
        return {"status": "failed", "run_id": run_id}
    finally:
        r.delete(lock_key)
