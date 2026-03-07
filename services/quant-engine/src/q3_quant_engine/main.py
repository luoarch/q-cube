from fastapi import FastAPI

app = FastAPI(title="Q3 Quant Engine", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"service": "quant-engine", "status": "ok"}
