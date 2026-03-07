from __future__ import annotations

from typing import Any


def resolve_scope(rows_by_scope: dict[str, list[Any]]) -> tuple[str, list[Any]]:
    """Prefer consolidated ('con') over individual ('ind') statements.

    Returns a tuple of (chosen_scope, rows).  Falls back to 'ind' with an
    empty list if neither scope is present.
    """
    if "con" in rows_by_scope and rows_by_scope["con"]:
        return "con", rows_by_scope["con"]
    if "ind" in rows_by_scope and rows_by_scope["ind"]:
        return "ind", rows_by_scope["ind"]
    return "ind", []
