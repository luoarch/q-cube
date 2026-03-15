"""Plan 2 thesis scoring engine — pure functions only."""

from __future__ import annotations

from q3_quant_engine.thesis.config import (
    BUCKET_THRESHOLDS,
    FRAGILITY_WEIGHTS,
    OPPORTUNITY_WEIGHTS,
    THESIS_RANK_WEIGHTS,
)
from q3_quant_engine.thesis.types import (
    Plan2Explanation,
    Plan2RankingSnapshot,
    ThesisBucket,
)


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def compute_final_commodity_affinity_score(
    direct: float,
    indirect: float,
    export_fx: float,
) -> float:
    """Weighted sum of opportunity dimensions. Returns 0-100."""
    raw = (
        OPPORTUNITY_WEIGHTS["direct_commodity_exposure"] * direct
        + OPPORTUNITY_WEIGHTS["indirect_commodity_exposure"] * indirect
        + OPPORTUNITY_WEIGHTS["export_fx_leverage"] * export_fx
    )
    return _clamp(raw)


def compute_final_dollar_fragility_score(
    refinancing_stress: float,
    usd_debt_exposure: float,
    usd_import_dependence: float,
    usd_revenue_offset: float,
) -> float:
    """Weighted sum of fragility dimensions. usd_revenue_offset is protective (inverted). Returns 0-100."""
    raw = (
        FRAGILITY_WEIGHTS["refinancing_stress"] * refinancing_stress
        + FRAGILITY_WEIGHTS["usd_debt_exposure"] * usd_debt_exposure
        + FRAGILITY_WEIGHTS["usd_import_dependence"] * usd_import_dependence
        + FRAGILITY_WEIGHTS["usd_revenue_offset_inverted"] * (100.0 - usd_revenue_offset)
    )
    return _clamp(raw)


def assign_thesis_bucket(
    direct_commodity_score: float,
    indirect_commodity_score: float,
    final_fragility_score: float,
) -> ThesisBucket:
    """Assign thesis bucket based on thresholds. Order: A > B > D > C (default)."""
    t = BUCKET_THRESHOLDS

    if (
        direct_commodity_score >= t["a_direct_min_direct_commodity"]
        and final_fragility_score <= t["a_direct_max_fragility"]
    ):
        return ThesisBucket.A_DIRECT

    if (
        indirect_commodity_score >= t["b_indirect_min_indirect_commodity"]
        and final_fragility_score <= t["b_indirect_max_fragility"]
    ):
        return ThesisBucket.B_INDIRECT

    if final_fragility_score >= t["d_fragile_min_fragility"]:
        return ThesisBucket.D_FRAGILE

    return ThesisBucket.C_NEUTRAL


def compute_thesis_rank_score(
    commodity_affinity: float,
    fragility: float,
    base_core: float,
) -> float:
    """Compute final thesis rank score. Returns 0-100."""
    raw = (
        THESIS_RANK_WEIGHTS["commodity_affinity"] * commodity_affinity
        + THESIS_RANK_WEIGHTS["fragility_inverted"] * (100.0 - fragility)
        + THESIS_RANK_WEIGHTS["base_core"] * base_core
    )
    return _clamp(raw)


_BUCKET_ORDER: dict[ThesisBucket, int] = {
    ThesisBucket.A_DIRECT: 1,
    ThesisBucket.B_INDIRECT: 2,
    ThesisBucket.C_NEUTRAL: 3,
    ThesisBucket.D_FRAGILE: 4,
}


def sort_plan2_rank(
    snapshots: list[Plan2RankingSnapshot],
) -> list[Plan2RankingSnapshot]:
    """Sort by bucket precedence (absolute), then thesis_rank_score descending.

    Ineligible assets are placed at the end, sorted by ticker for stability.
    """

    def _sort_key(s: Plan2RankingSnapshot) -> tuple[int, float, str]:
        if not s.eligible or s.bucket is None or s.thesis_rank_score is None:
            return (99, 0.0, s.ticker)
        return (_BUCKET_ORDER[s.bucket], -s.thesis_rank_score, s.ticker)

    sorted_list = sorted(snapshots, key=_sort_key)

    # Assign thesis_rank (1-based) for eligible assets only
    rank = 1
    for s in sorted_list:
        if s.eligible and s.bucket is not None:
            s.thesis_rank = rank
            rank += 1

    return sorted_list


def generate_explanation(
    ticker: str,
    bucket: ThesisBucket,
    thesis_rank_score: float,
    commodity_affinity: float,
    fragility: float,
    base_core: float,
    direct_commodity: float,
    indirect_commodity: float,
    export_fx: float,
    refinancing_stress: float,
    usd_debt: float,
    usd_import: float,
    usd_revenue_offset: float,
) -> Plan2Explanation:
    """Generate deterministic template-based explanation. Pure function."""
    positives: list[str] = []
    negatives: list[str] = []

    # Opportunity positives
    if direct_commodity >= 70:
        positives.append("Alta exposicao direta a commodities")
    elif direct_commodity >= 40:
        positives.append("Exposicao moderada a commodities")

    if indirect_commodity >= 60:
        positives.append("Captura indireta relevante do ciclo de commodities")

    if export_fx >= 60:
        positives.append("Forte alavancagem de exportacao/receita em moeda forte")
    elif export_fx >= 30:
        positives.append("Alguma exposicao a exportacao/moeda forte")

    if base_core >= 70:
        positives.append("Bem posicionada no ranking core (value + quality)")

    # Fragility negatives
    if refinancing_stress >= 70:
        negatives.append("Estresse de refinanciamento elevado")
    elif refinancing_stress >= 40:
        negatives.append("Pressao moderada de refinanciamento")

    if usd_debt >= 70:
        negatives.append("Alta exposicao de divida em USD")
    elif usd_debt >= 40:
        negatives.append("Exposicao moderada de divida em USD")

    if usd_import >= 70:
        negatives.append("Alta dependencia de importacoes dolarizadas")

    if usd_revenue_offset < 30:
        negatives.append("Baixa protecao de receita em USD (hedge natural fraco)")

    if fragility >= 75:
        negatives.append("Fragilidade geral alta ao regime do dolar/funding")
    elif fragility >= 50:
        negatives.append("Fragilidade moderada ao regime do dolar")

    # Summary
    bucket_labels = {
        ThesisBucket.A_DIRECT: "Empresa diretamente alavancada ao ciclo de commodities",
        ThesisBucket.B_INDIRECT: "Empresa com captura indireta do ciclo de commodities",
        ThesisBucket.C_NEUTRAL: "Empresa com baixa aderencia a tese de commodities",
        ThesisBucket.D_FRAGILE: "Empresa com fragilidade relevante ao regime do dolar/funding",
    }

    fragility_label = (
        "fragilidade controlada ao dolar"
        if fragility < 50
        else "fragilidade moderada ao dolar"
        if fragility < 75
        else "fragilidade elevada ao dolar"
    )

    summary = f"{bucket_labels[bucket]}, com {fragility_label}."

    return Plan2Explanation(
        ticker=ticker,
        bucket=bucket,
        thesis_rank_score=thesis_rank_score,
        positives=positives,
        negatives=negatives,
        summary=summary,
    )
