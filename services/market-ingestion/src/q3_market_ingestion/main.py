from fastapi import FastAPI

from q3_market_ingestion.handlers.ingest import router as ingest_router

app = FastAPI(title="Q3 Market Ingestion", version="0.1.0")
app.include_router(ingest_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "market-ingestion", "status": "ok"}
