from fastapi import FastAPI

app = FastAPI(title="Q3 Market Ingestion", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "market-ingestion", "status": "ok"}
