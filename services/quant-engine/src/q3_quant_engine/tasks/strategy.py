import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from q3_quant_engine.celery_app import celery_app
from q3_quant_engine.db.session import SessionLocal
from q3_quant_engine.models.entities import Job, RunStatus, StrategyRun
from q3_quant_engine.strategies.ranking import run_strategy
from q3_shared_models.entities import BacktestRun

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@celery_app.task(name="q3_quant_engine.tasks.strategy.run_strategy_task")
def run_strategy_task(
    job_id: str,
    run_id: str,
    tenant_id: str,
    strategy: str,
) -> dict[str, str]:
    parsed_run_id = uuid.UUID(run_id)
    parsed_job_id = uuid.UUID(job_id)
    parsed_tenant_id = uuid.UUID(tenant_id)

    with SessionLocal() as session:
        try:
            run = session.execute(
                select(StrategyRun).where(
                    StrategyRun.id == parsed_run_id,
                    StrategyRun.tenant_id == parsed_tenant_id,
                )
            ).scalar_one()
            job = session.execute(
                select(Job).where(
                    Job.id == parsed_job_id,
                    Job.tenant_id == parsed_tenant_id,
                )
            ).scalar_one()

            run.status = RunStatus.running
            job.status = RunStatus.running
            session.commit()

            ranked_assets = run_strategy(session, parsed_tenant_id, strategy)

            # Run refiner on top 30 (deterministic, no LLM)
            try:
                from q3_quant_engine.refiner.engine import RefinerEngine
                refiner = RefinerEngine(session)
                refiner.refine(
                    run_id=parsed_run_id,
                    tenant_id=parsed_tenant_id,
                    top_n=30,
                    ranked_assets=ranked_assets,
                )
            except Exception as refiner_exc:  # noqa: BLE001
                logger.warning("Refiner failed (non-fatal) run=%s: %s", run_id, refiner_exc)

            run.status = RunStatus.completed
            run.result_json = {
                "strategy": strategy,
                "totalRanked": len(ranked_assets),
                "rankedAssets": ranked_assets,
                "generatedAt": _now_iso(),
            }

            # Index results into RAG embeddings (non-fatal)
            try:
                from q3_ai_assistant.rag.auto_indexer import index_refiner_results, index_strategy_run
                index_strategy_run(session, parsed_run_id)
                index_refiner_results(session, str(parsed_run_id))
            except Exception as rag_exc:  # noqa: BLE001
                logger.warning("RAG indexing failed (non-fatal) run=%s: %s", run_id, rag_exc)
            run.error_message = None

            job.status = RunStatus.completed
            job.error_message = None

            session.commit()
            logger.info("completed run=%s strategy=%s assets=%d", run_id, strategy, len(ranked_assets))

            return {"run_id": run_id, "status": "completed"}

        except Exception as exc:  # noqa: BLE001
            session.rollback()

            run = session.execute(
                select(StrategyRun).where(
                    StrategyRun.id == parsed_run_id,
                    StrategyRun.tenant_id == parsed_tenant_id,
                )
            ).scalar_one_or_none()
            job = session.execute(
                select(Job).where(
                    Job.id == parsed_job_id,
                    Job.tenant_id == parsed_tenant_id,
                )
            ).scalar_one_or_none()

            if run is not None:
                run.status = RunStatus.failed
                run.error_message = str(exc)

            if job is not None:
                job.status = RunStatus.failed
                job.error_message = str(exc)

            session.commit()
            logger.exception("failed run=%s", run_id)

            return {"run_id": run_id, "status": "failed", "error": str(exc)}


@celery_app.task(name="q3_quant_engine.tasks.strategy.backtest_run_task")
def backtest_run_task(
    job_id: str,
    run_id: str,
    tenant_id: str,
    config_payload: dict,
) -> dict[str, str]:
    """Execute a backtest and persist results to backtest_runs."""
    from datetime import date as date_type
    from q3_quant_engine.backtest.costs import CostModel
    from q3_quant_engine.backtest.engine import BacktestConfig, run_backtest

    parsed_run_id = uuid.UUID(run_id)
    parsed_job_id = uuid.UUID(job_id)
    parsed_tenant_id = uuid.UUID(tenant_id)

    with SessionLocal() as session:
        try:
            bt_run = session.execute(
                select(BacktestRun).where(
                    BacktestRun.id == parsed_run_id,
                    BacktestRun.tenant_id == parsed_tenant_id,
                )
            ).scalar_one()
            job = session.execute(
                select(Job).where(
                    Job.id == parsed_job_id,
                    Job.tenant_id == parsed_tenant_id,
                )
            ).scalar_one()

            bt_run.status = RunStatus.running
            job.status = RunStatus.running
            session.commit()

            # API sends camelCase keys; support both camelCase and snake_case
            def _get(key_snake: str, key_camel: str, default=None):  # type: ignore[no-untyped-def]
                return config_payload.get(key_camel, config_payload.get(key_snake, default))

            cost_cfg = _get("cost_model", "costModel") or {}
            cost_model = CostModel(
                fixed_cost_per_trade=cost_cfg.get("fixedCostPerTrade", cost_cfg.get("fixed_cost_per_trade", 0.0)),
                proportional_cost=cost_cfg.get("proportionalCost", cost_cfg.get("proportional_cost", 0.0005)),
                slippage_bps=cost_cfg.get("slippageBps", cost_cfg.get("slippage_bps", 10.0)),
            )

            config = BacktestConfig(
                strategy_type=_get("strategy_type", "strategyType"),
                start_date=date_type.fromisoformat(_get("start_date", "startDate")),
                end_date=date_type.fromisoformat(_get("end_date", "endDate")),
                rebalance_freq=_get("rebalance_freq", "rebalanceFreq", "monthly"),
                execution_lag_days=_get("execution_lag_days", "executionLagDays", 1),
                top_n=_get("top_n", "topN", 20),
                equal_weight=_get("equal_weight", "equalWeight", True),
                cost_model=cost_model,
                initial_capital=_get("initial_capital", "initialCapital", 1_000_000.0),
                benchmark=_get("benchmark", "benchmark"),
            )

            result = run_backtest(session, config)

            # Serialize dates in equity curve and trades
            equity_curve = [
                {"date": str(p["date"]), "value": p["value"]}
                for p in result.equity_curve
            ]
            trades = [
                {**t, "date": str(t["date"])} for t in result.trades
            ]

            # Convert snake_case metrics to camelCase for Zod schema
            raw_m = result.metrics
            metrics_camel = {
                "cagr": raw_m.get("cagr", 0.0),
                "volatility": raw_m.get("volatility", 0.0),
                "sharpe": raw_m.get("sharpe", 0.0),
                "sortino": raw_m.get("sortino", 0.0),
                "maxDrawdown": raw_m.get("max_drawdown", 0.0),
                "maxDrawdownDurationDays": raw_m.get("max_drawdown_duration_days", 0),
                "turnoverAvg": raw_m.get("turnover_avg", 0.0),
                "hitRate": raw_m.get("hit_rate", 0.0),
                "totalCosts": raw_m.get("total_costs", 0.0),
            }
            if "excess_return" in raw_m:
                metrics_camel["excessReturn"] = raw_m["excess_return"]
            if "tracking_error" in raw_m:
                metrics_camel["trackingError"] = raw_m["tracking_error"]
            if "information_ratio" in raw_m:
                metrics_camel["informationRatio"] = raw_m["information_ratio"]

            bt_run.status = RunStatus.completed
            bt_run.metrics_json = {
                "metrics": metrics_camel,
                "equityCurve": equity_curve,
                "tradesCount": len(trades),
                "rebalanceCount": len(result.rebalance_dates),
            }

            job.status = RunStatus.completed
            job.error_message = None
            session.commit()

            logger.info("completed backtest run=%s strategy=%s", run_id, config.strategy_type)
            return {"run_id": run_id, "status": "completed"}

        except Exception as exc:  # noqa: BLE001
            session.rollback()

            bt_run = session.execute(
                select(BacktestRun).where(BacktestRun.id == parsed_run_id)
            ).scalar_one_or_none()
            job = session.execute(
                select(Job).where(Job.id == parsed_job_id)
            ).scalar_one_or_none()

            if bt_run is not None:
                bt_run.status = RunStatus.failed
                bt_run.error_message = str(exc)
            if job is not None:
                job.status = RunStatus.failed
                job.error_message = str(exc)

            session.commit()
            logger.exception("failed backtest run=%s", run_id)
            return {"run_id": run_id, "status": "failed", "error": str(exc)}
