from fastapi import FastAPI

from q3_fundamentals_engine.handlers.batch import router as batch_router
from q3_fundamentals_engine.handlers.filings import router as filings_router
from q3_fundamentals_engine.handlers.issuers import router as issuers_router
from q3_fundamentals_engine.handlers.metrics import router as metrics_router

app = FastAPI(title="Q3 Fundamentals Engine", version="0.1.0")
app.include_router(batch_router)
app.include_router(issuers_router)
app.include_router(filings_router)
app.include_router(metrics_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "fundamentals-engine", "status": "ok"}
