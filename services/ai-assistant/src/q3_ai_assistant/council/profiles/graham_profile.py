"""Graham-inspired strategy profile — margem de seguranca, preco vs valor."""

from q3_ai_assistant.council.profiles.base import (
    HardRejectRule,
    SoftPreference,
    StrategyProfile,
)

GRAHAM_PROFILE = StrategyProfile(
    agent_id="graham",
    display_name="Graham-inspired",
    philosophy="Margem de seguranca, preco abaixo do valor intrinseco, conservadorismo",
    profile_version=1,
    core_metrics=[
        "earnings_yield",
        "debt_to_ebitda",
        "net_debt",
        "gross_margin",
        "net_margin",
        "roic",
    ],
    hard_rejects=[
        HardRejectRule(
            code="high_leverage_expensive",
            description="Divida/EBITDA > 5x combinada com earnings yield < 5%",
            condition="debt_to_ebitda > 5.0 AND earnings_yield < 0.05 (non-financial only)",
        ),
        HardRejectRule(
            code="negative_equity",
            description="Patrimonio liquido negativo",
            condition="equity < 0",
        ),
    ],
    soft_preferences=[
        SoftPreference(
            code="prefers_low_debt",
            description="Prefere empresas com baixo endividamento",
            weight="strong",
        ),
        SoftPreference(
            code="prefers_margin_of_safety",
            description="Exige desconto significativo vs valor intrinseco",
            weight="strong",
        ),
        SoftPreference(
            code="dislikes_growth_stories",
            description="Desconfia de narrativas de crescimento sem lastro",
            weight="moderate",
        ),
        SoftPreference(
            code="prefers_quantitative_analysis",
            description="Valoriza dados quantitativos sobre qualitativos",
            weight="moderate",
        ),
    ],
    classification_aware=True,
    sector_exceptions=["bank", "insurer", "holding"],
)
