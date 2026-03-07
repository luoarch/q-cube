import logging
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from q3_quant_engine.celery_app import celery_app
from q3_quant_engine.db.session import SessionLocal
from q3_quant_engine.models.entities import Job, RunStatus, StrategyRun

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

            # Placeholder for real quant execution.
            time.sleep(1)

            run.status = RunStatus.completed
            run.result_json = {
                "strategy": strategy,
                "rankedAssets": ["PETR4", "VALE3", "WEGE3"],
                "generatedAt": _now_iso(),
            }
            run.error_message = None

            job.status = RunStatus.completed
            job.error_message = None

            session.commit()
            logger.info("completed run=%s", run_id)

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
