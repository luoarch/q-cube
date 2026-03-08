"""Buffett-inspired strategy profile — qualidade, moat, alocacao de capital."""

from q3_ai_assistant.council.profiles.base import (
    HardRejectRule,
    SoftPreference,
    StrategyProfile,
)

BUFFETT_PROFILE = StrategyProfile(
    agent_id="buffett",
    display_name="Buffett-inspired",
    philosophy="Qualidade do negocio, moat competitivo, ROE consistente, longo prazo",
    profile_version=1,
    core_metrics=[
        "roe",
        "gross_margin",
        "ebit_margin",
        "net_margin",
        "cash_from_operations",
        "roic",
        "cash_conversion",
    ],
    hard_rejects=[
        HardRejectRule(
            code="roe_consistently_low",
            description="ROE abaixo de 8% de forma consistente",
            condition="roe < 0.08 for all of last 2+ annual periods",
        ),
        HardRejectRule(
            code="margin_collapse",
            description="Margem bruta caiu mais de 30% no periodo",
            condition="gross_margin[-1] < gross_margin[0] * 0.7 over 3 periods",
        ),
    ],
    soft_preferences=[
        SoftPreference(
            code="prefers_high_roe_consistency",
            description="Prefere ROE alto e consistente ao longo dos anos",
            weight="strong",
        ),
        SoftPreference(
            code="prefers_stable_margins",
            description="Valoriza margens estaveis ou crescentes",
            weight="strong",
        ),
        SoftPreference(
            code="prefers_strong_fcf",
            description="Prefere FCF forte e previsivel",
            weight="strong",
        ),
        SoftPreference(
            code="prefers_good_management",
            description="Valoriza boa alocacao de capital pelo management",
            weight="moderate",
        ),
        SoftPreference(
            code="prefers_moat",
            description="Prefere empresas com vantagens competitivas duraveis",
            weight="strong",
        ),
    ],
    classification_aware=True,
)
