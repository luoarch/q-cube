from __future__ import annotations

NEGATIVE_KEYS: set[str] = {"cost_of_goods_sold", "operating_expenses", "income_tax"}


def normalize_sign(canonical_key: str | None, value: float | None) -> float | None:
    """Normalize signs for accounting consistency.

    Expenses (cost_of_goods_sold, operating_expenses, income_tax) should be
    stored as negative values. If a positive value is reported for these keys,
    it is flipped to negative. All other keys keep their reported sign.
    """
    if value is None or canonical_key is None:
        return value
    if canonical_key in NEGATIVE_KEYS and value > 0:
        return -value
    return value
