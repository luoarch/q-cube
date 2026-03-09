"""Cost budget enforcement for AI operations.

Tracks and enforces:
- Per-session token/cost limits
- Daily tenant-level cost caps
- Alerts when approaching limits
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Default limits
DEFAULT_SESSION_MAX_TOKENS = 100_000
DEFAULT_SESSION_MAX_COST_USD = 2.0
DEFAULT_DAILY_TENANT_MAX_COST_USD = 10.0
ALERT_THRESHOLD = 0.8  # Alert at 80% of limit


@dataclass(frozen=True)
class BudgetStatus:
    """Current budget status for a session or tenant."""
    total_tokens: int
    total_cost_usd: float
    limit_tokens: int
    limit_cost_usd: float
    tokens_remaining: int
    cost_remaining: float
    is_exceeded: bool
    is_near_limit: bool
    period: str  # 'session' or 'daily'


class CostBudget:
    """Enforce cost and token budgets."""

    def __init__(
        self,
        *,
        session_max_tokens: int = DEFAULT_SESSION_MAX_TOKENS,
        session_max_cost_usd: float = DEFAULT_SESSION_MAX_COST_USD,
        daily_max_cost_usd: float = DEFAULT_DAILY_TENANT_MAX_COST_USD,
    ) -> None:
        self._session_max_tokens = session_max_tokens
        self._session_max_cost_usd = session_max_cost_usd
        self._daily_max_cost_usd = daily_max_cost_usd

    def check_session_budget(
        self,
        db: Session,
        session_id: str,
    ) -> BudgetStatus:
        """Check if a chat session is within budget."""
        from q3_shared_models.entities import ChatMessage

        result = (
            db.query(
                func.coalesce(func.sum(ChatMessage.tokens_used), 0),
                func.coalesce(func.sum(ChatMessage.cost_usd), 0),
            )
            .filter(ChatMessage.session_id == session_id)
            .one()
        )

        total_tokens = int(result[0])
        total_cost = float(result[1])

        tokens_remaining = max(0, self._session_max_tokens - total_tokens)
        cost_remaining = max(0.0, self._session_max_cost_usd - total_cost)

        is_exceeded = total_tokens >= self._session_max_tokens or total_cost >= self._session_max_cost_usd
        is_near = (
            total_tokens >= self._session_max_tokens * ALERT_THRESHOLD
            or total_cost >= self._session_max_cost_usd * ALERT_THRESHOLD
        )

        return BudgetStatus(
            total_tokens=total_tokens,
            total_cost_usd=total_cost,
            limit_tokens=self._session_max_tokens,
            limit_cost_usd=self._session_max_cost_usd,
            tokens_remaining=tokens_remaining,
            cost_remaining=cost_remaining,
            is_exceeded=is_exceeded,
            is_near_limit=is_near,
            period="session",
        )

    def check_daily_budget(
        self,
        db: Session,
        tenant_id: str,
    ) -> BudgetStatus:
        """Check if a tenant is within daily budget."""
        today = datetime.now(timezone.utc).date()

        result = db.execute(
            text("""
                SELECT
                    COALESCE(SUM(tokens), 0),
                    COALESCE(SUM(cost), 0)
                FROM (
                    SELECT cm.tokens_used AS tokens, cm.cost_usd AS cost
                    FROM chat_messages cm
                    JOIN chat_sessions cs ON cs.id = cm.session_id
                    WHERE cs.tenant_id = :tenant_id
                    AND cm.created_at >= :today
                    UNION ALL
                    SELECT 0 AS tokens, co.cost_usd AS cost
                    FROM council_opinions co
                    JOIN council_sessions ccs ON ccs.id = co.council_session_id
                    WHERE ccs.tenant_id = :tenant_id
                    AND co.created_at >= :today
                ) combined
            """),
            {"tenant_id": tenant_id, "today": str(today)},
        ).one()

        total_tokens = int(result[0])
        total_cost = float(result[1])

        cost_remaining = max(0.0, self._daily_max_cost_usd - total_cost)
        is_exceeded = total_cost >= self._daily_max_cost_usd
        is_near = total_cost >= self._daily_max_cost_usd * ALERT_THRESHOLD

        return BudgetStatus(
            total_tokens=total_tokens,
            total_cost_usd=total_cost,
            limit_tokens=0,  # No daily token limit, only cost
            limit_cost_usd=self._daily_max_cost_usd,
            tokens_remaining=0,
            cost_remaining=cost_remaining,
            is_exceeded=is_exceeded,
            is_near_limit=is_near,
            period="daily",
        )

    def can_proceed(
        self,
        db: Session,
        session_id: str,
        tenant_id: str,
    ) -> tuple[bool, str | None]:
        """Check both session and daily budgets. Returns (ok, reason)."""
        session_status = self.check_session_budget(db, session_id)
        if session_status.is_exceeded:
            logger.warning("Session %s exceeded budget: %s tokens, $%.4f",
                          session_id, session_status.total_tokens, session_status.total_cost_usd)
            return False, "Session budget exceeded. Start a new session."

        daily_status = self.check_daily_budget(db, tenant_id)
        if daily_status.is_exceeded:
            logger.warning("Tenant %s exceeded daily budget: $%.4f",
                          tenant_id, daily_status.total_cost_usd)
            return False, "Daily cost limit reached. Try again tomorrow."

        if session_status.is_near_limit:
            logger.info("Session %s approaching budget limit", session_id)

        return True, None
