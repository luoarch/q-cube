"""Greenblatt-inspired strategy profile — earnings yield, return on capital."""

from q3_ai_assistant.council.profiles.base import (
    HardRejectRule,
    SoftPreference,
    StrategyProfile,
)

GREENBLATT_PROFILE = StrategyProfile(
    agent_id="greenblatt",
    display_name="Greenblatt-inspired",
    philosophy="Magic Formula — empresas boas a precos bons via EY + ROIC",
    profile_version=1,
    core_metrics=[
        "earnings_yield",
        "roic",
        "ebit",
        "ebit_margin",
        "enterprise_value",
    ],
    hard_rejects=[
        HardRejectRule(
            code="negative_ebit",
            description="EBIT negativo — nao atende criterio Magic Formula",
            condition="ebit <= 0 (latest period)",
        ),
        HardRejectRule(
            code="roic_consistently_low",
            description="ROIC abaixo de 5% nos ultimos periodos",
            condition="roic < 0.05 for all of last 2+ annual periods",
        ),
    ],
    soft_preferences=[
        SoftPreference(
            code="prefers_high_roic",
            description="Prefere ROIC alto e consistente",
            weight="strong",
        ),
        SoftPreference(
            code="prefers_systematic_ranking",
            description="Valoriza ranking sistematico sobre narrativas",
            weight="strong",
        ),
        SoftPreference(
            code="prefers_ebit_driven",
            description="Foco em EBIT como proxy de poder de lucro",
            weight="moderate",
        ),
    ],
    classification_aware=True,
)
