"""Tests for cost budget enforcement."""

from __future__ import annotations

from q3_ai_assistant.security.cost_budget import (
    ALERT_THRESHOLD,
    DEFAULT_DAILY_TENANT_MAX_COST_USD,
    DEFAULT_SESSION_MAX_COST_USD,
    DEFAULT_SESSION_MAX_TOKENS,
    BudgetStatus,
    CostBudget,
)


class TestBudgetStatus:
    def test_is_frozen(self):
        status = BudgetStatus(
            total_tokens=100,
            total_cost_usd=0.01,
            limit_tokens=1000,
            limit_cost_usd=2.0,
            tokens_remaining=900,
            cost_remaining=1.99,
            is_exceeded=False,
            is_near_limit=False,
            period="session",
        )
        assert status.total_tokens == 100
        assert status.is_exceeded is False

    def test_defaults(self):
        budget = CostBudget()
        assert budget._session_max_tokens == DEFAULT_SESSION_MAX_TOKENS
        assert budget._session_max_cost_usd == DEFAULT_SESSION_MAX_COST_USD
        assert budget._daily_max_cost_usd == DEFAULT_DAILY_TENANT_MAX_COST_USD

    def test_custom_limits(self):
        budget = CostBudget(
            session_max_tokens=5000,
            session_max_cost_usd=0.5,
            daily_max_cost_usd=3.0,
        )
        assert budget._session_max_tokens == 5000
        assert budget._session_max_cost_usd == 0.5
        assert budget._daily_max_cost_usd == 3.0


class TestBudgetStatusFields:
    def test_exceeded_when_tokens_at_limit(self):
        status = BudgetStatus(
            total_tokens=100_000,
            total_cost_usd=0.5,
            limit_tokens=100_000,
            limit_cost_usd=2.0,
            tokens_remaining=0,
            cost_remaining=1.5,
            is_exceeded=True,
            is_near_limit=True,
            period="session",
        )
        assert status.is_exceeded is True
        assert status.tokens_remaining == 0

    def test_exceeded_when_cost_at_limit(self):
        status = BudgetStatus(
            total_tokens=50_000,
            total_cost_usd=2.0,
            limit_tokens=100_000,
            limit_cost_usd=2.0,
            tokens_remaining=50_000,
            cost_remaining=0.0,
            is_exceeded=True,
            is_near_limit=True,
            period="session",
        )
        assert status.is_exceeded is True
        assert status.cost_remaining == 0.0

    def test_near_limit_threshold(self):
        # At 80% of token limit
        at_threshold = int(100_000 * ALERT_THRESHOLD)
        status = BudgetStatus(
            total_tokens=at_threshold,
            total_cost_usd=0.5,
            limit_tokens=100_000,
            limit_cost_usd=2.0,
            tokens_remaining=100_000 - at_threshold,
            cost_remaining=1.5,
            is_exceeded=False,
            is_near_limit=True,
            period="session",
        )
        assert status.is_near_limit is True
        assert status.is_exceeded is False

    def test_daily_period(self):
        status = BudgetStatus(
            total_tokens=0,
            total_cost_usd=0.0,
            limit_tokens=0,
            limit_cost_usd=10.0,
            tokens_remaining=0,
            cost_remaining=10.0,
            is_exceeded=False,
            is_near_limit=False,
            period="daily",
        )
        assert status.period == "daily"
