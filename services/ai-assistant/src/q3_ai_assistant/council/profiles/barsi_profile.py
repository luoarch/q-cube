"""Barsi-inspired strategy profile — dividendos, renda passiva, perenidade."""

from q3_ai_assistant.council.profiles.base import (
    HardRejectRule,
    SoftPreference,
    StrategyProfile,
)

BARSI_PROFILE = StrategyProfile(
    agent_id="barsi",
    display_name="Barsi-inspired",
    philosophy="Foco em dividendos consistentes, renda passiva e empresas perenes",
    profile_version=1,
    core_metrics=[
        "earnings_yield",
        "net_income",
        "cash_from_operations",
        "cash_from_investing",
        "net_margin",
        "debt_to_ebitda",
    ],
    hard_rejects=[
        HardRejectRule(
            code="negative_fcf_3y",
            description="Fluxo de caixa livre negativo nos ultimos 3 anos",
            condition="CFO + CFI < 0 for all of last 3 annual periods",
        ),
        HardRejectRule(
            code="negative_ni_recurring",
            description="Prejuizo recorrente (2+ dos ultimos 3 anos)",
            condition="net_income < 0 in 2+ of last 3 annual periods",
        ),
    ],
    soft_preferences=[
        SoftPreference(
            code="prefers_utilities",
            description="Prefere utilities, bancos e seguradoras (perenidade)",
            weight="strong",
        ),
        SoftPreference(
            code="prefers_dividend_payers",
            description="Prefere empresas com historico de dividendos",
            weight="strong",
        ),
        SoftPreference(
            code="prefers_recurring_revenue",
            description="Prefere receita recorrente e previsivel",
            weight="moderate",
        ),
        SoftPreference(
            code="dislikes_high_growth_no_profit",
            description="Desconfia de growth sem lucro distribuivel",
            weight="moderate",
        ),
    ],
    classification_aware=True,
    sector_exceptions=["bank", "insurer"],
)
