"""Decision engine FastAPI router."""
from __future__ import annotations

import dataclasses

from fastapi import APIRouter, HTTPException

from q3_quant_engine.db.session import SessionLocal
from q3_quant_engine.decision.engine import compute_ticker_decision

router = APIRouter(prefix="/decision", tags=["decision"])


def _to_dict(obj):
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_dict(i) for i in obj]
    if isinstance(obj, tuple):
        return list(obj)
    if hasattr(obj, "value") and not isinstance(obj, (str, int, float, bool)):
        return obj.value
    return obj


@router.get("/{ticker}")
def get_ticker_decision(ticker: str):
    """Compute and return a ticker decision."""
    with SessionLocal() as session:
        td = compute_ticker_decision(session, ticker.upper())

    result = _to_dict(td)

    # camelCase keys for API consumers
    def _camel(d):
        if isinstance(d, dict):
            return {
                "".join(w.capitalize() if i else w for i, w in enumerate(k.split("_"))): _camel(v)
                for k, v in d.items()
            }
        if isinstance(d, list):
            return [_camel(i) for i in d]
        return d

    return _camel(result)
