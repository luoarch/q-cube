import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from q3_quant_engine.queue_poller import start_poller

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    logger.info("Starting queue poller…")
    start_poller()
    yield
    logger.info("Shutting down (poller thread is daemon, will exit with process)")


app = FastAPI(title="Q3 Quant Engine", version="0.1.0", lifespan=lifespan)

# Plan 2 internal API
from q3_quant_engine.thesis.router import router as plan2_router  # noqa: E402

app.include_router(plan2_router)

# Ticker Decision Engine API
from q3_quant_engine.decision.router import router as decision_router  # noqa: E402

app.include_router(decision_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "quant-engine", "status": "ok"}
