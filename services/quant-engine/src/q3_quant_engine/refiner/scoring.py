"""Refiner scoring blocks — four deterministic 0–1 scores.

Each block uses 3-period trends from computed_metrics + statement_lines.
"""

from __future__ import annotations

import statistics

from q3_quant_engine.refiner.types import PeriodValue, ScoringBlock


def _latest(series: list[PeriodValue]) -> float | None:
    if not series:
        return None
    return series[-1].value


def _values(series: list[PeriodValue]) -> list[float]:
    return [pv.value for pv in series if pv.value is not None]


def _trend_score(series: list[PeriodValue]) -> float | None:
    """Score trend direction: improving = higher, deteriorating = lower.

    Returns 0–1 where 1.0 = consistently improving, 0.0 = consistently worsening.
    """
    vals = _values(series)
    if len(vals) < 2:
        return None
    improvements = sum(1 for a, b in zip(vals, vals[1:]) if b > a)
    total = len(vals) - 1
    return improvements / total


def _trend_score_lower_better(series: list[PeriodValue]) -> float | None:
    """Trend score where decreasing is good (e.g., debt ratios)."""
    vals = _values(series)
    if len(vals) < 2:
        return None
    improvements = sum(1 for a, b in zip(vals, vals[1:]) if b < a)
    total = len(vals) - 1
    return improvements / total


def _stability_score(series: list[PeriodValue]) -> float | None:
    """Score stability as inverse of coefficient of variation. Higher = more stable."""
    vals = _values(series)
    if len(vals) < 2:
        return None
    mean = statistics.mean(vals)
    if mean == 0:
        return 0.5
    stdev = statistics.stdev(vals)
    cv = abs(stdev / mean)
    # Map CV to 0–1: CV=0 -> 1.0, CV>=1 -> 0.0
    return max(0.0, min(1.0, 1.0 - cv))


def _level_score(value: float | None, low: float, high: float) -> float:
    """Map a value into 0–1 range based on thresholds."""
    if value is None:
        return 0.5
    if value <= low:
        return 0.0
    if value >= high:
        return 1.0
    return (value - low) / (high - low)


def _safe_div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return a / b


def _avg(scores: list[float | None]) -> float:
    """Average of non-None scores, defaulting to 0.5 (neutral) if all None."""
    valid = [s for s in scores if s is not None]
    if not valid:
        return 0.5
    return sum(valid) / len(valid)


def score_earnings_quality(data: dict[str, list[PeriodValue]]) -> ScoringBlock:
    """Block A: Earnings quality — cash conversion, CFO vs NI, FCF proxy, operating cash quality."""
    # 1. Cash conversion trend
    cc_trend = _trend_score(data.get("cash_conversion", []))

    # 2. CFO vs net income consistency
    cfo_series = data.get("cash_from_operations", [])
    ni_series = data.get("net_income", [])
    cfo_ni_ratio: float | None = None
    if cfo_series and ni_series:
        ratios = []
        for cfo_pv, ni_pv in zip(cfo_series, ni_series):
            r = _safe_div(cfo_pv.value, ni_pv.value)
            if r is not None:
                ratios.append(r)
        if ratios:
            avg_ratio = statistics.mean(ratios)
            cfo_ni_ratio = _level_score(avg_ratio, 0.5, 1.5)

    # 3. FCF proxy trend: CFO + cash_from_investing
    cfi_series = data.get("cash_from_investing", [])
    fcf_values: list[PeriodValue] = []
    if cfo_series and cfi_series:
        for cfo_pv, cfi_pv in zip(cfo_series, cfi_series):
            if cfo_pv.value is not None and cfi_pv.value is not None:
                fcf_values.append(PeriodValue(
                    reference_date=cfo_pv.reference_date,
                    value=cfo_pv.value + cfi_pv.value,
                ))
    fcf_trend = _trend_score(fcf_values) if fcf_values else None

    # 4. Operating cash quality: CFO / revenue ratio trend
    rev_series = data.get("revenue", [])
    cfo_rev_values: list[PeriodValue] = []
    if cfo_series and rev_series:
        for cfo_pv, rev_pv in zip(cfo_series, rev_series):
            r = _safe_div(cfo_pv.value, rev_pv.value)
            if r is not None:
                cfo_rev_values.append(PeriodValue(
                    reference_date=cfo_pv.reference_date,
                    value=r,
                ))
    cfo_rev_trend = _trend_score(cfo_rev_values) if cfo_rev_values else None

    score = _avg([cc_trend, cfo_ni_ratio, fcf_trend, cfo_rev_trend])

    return ScoringBlock(
        name="earnings_quality",
        score=round(max(0.0, min(1.0, score)), 4),
        components={
            "cash_conversion_trend": cc_trend,
            "cfo_ni_consistency": cfo_ni_ratio,
            "fcf_proxy_trend": fcf_trend,
            "cfo_revenue_trend": cfo_rev_trend,
        },
    )


def score_safety(data: dict[str, list[PeriodValue]], classification: str) -> ScoringBlock:
    """Block B: Safety — debt trends, interest coverage, cash ratios.

    Bank/insurer/holding: uses fallback scoring (equity ratio, ROE stability).
    """
    if classification in ("bank", "insurer", "holding"):
        return _score_safety_bank(data)
    return _score_safety_standard(data)


def _score_safety_standard(data: dict[str, list[PeriodValue]]) -> ScoringBlock:
    # 1. Net debt trend (lower = better)
    nd_trend = _trend_score_lower_better(data.get("net_debt", []))

    # 2. Debt/EBITDA trend (lower = better)
    dte_trend = _trend_score_lower_better(data.get("debt_to_ebitda", []))

    # 3. Interest coverage: EBIT / abs(financial_result)
    ebit_series = data.get("ebit", [])
    fr_series = data.get("financial_result", [])
    ic_values: list[PeriodValue] = []
    if ebit_series and fr_series:
        for ebit_pv, fr_pv in zip(ebit_series, fr_series):
            if ebit_pv.value is not None and fr_pv.value is not None and fr_pv.value != 0:
                ic_values.append(PeriodValue(
                    reference_date=ebit_pv.reference_date,
                    value=ebit_pv.value / abs(fr_pv.value),
                ))
    ic_level: float | None = None
    if ic_values:
        latest_ic = ic_values[-1].value
        ic_level = _level_score(latest_ic, 1.5, 5.0)

    # 4. Cash / short-term debt ratio
    cash_series = data.get("cash_and_equivalents", [])
    std_series = data.get("short_term_debt", [])
    cash_std: float | None = None
    if cash_series and std_series:
        latest_cash = _latest(cash_series)
        latest_std = _latest(std_series)
        ratio = _safe_div(latest_cash, latest_std)
        if ratio is not None:
            cash_std = _level_score(ratio, 0.3, 2.0)

    score = _avg([nd_trend, dte_trend, ic_level, cash_std])

    return ScoringBlock(
        name="safety",
        score=round(max(0.0, min(1.0, score)), 4),
        components={
            "net_debt_trend": nd_trend,
            "debt_ebitda_trend": dte_trend,
            "interest_coverage_level": ic_level,
            "cash_short_term_debt": cash_std,
        },
    )


def _score_safety_bank(data: dict[str, list[PeriodValue]]) -> ScoringBlock:
    """Bank-specific safety: equity ratio trend, ROE stability."""
    # Equity / total_assets trend
    equity_series = data.get("equity", [])
    ta_series = data.get("total_assets", [])
    eq_ratio_values: list[PeriodValue] = []
    if equity_series and ta_series:
        for eq_pv, ta_pv in zip(equity_series, ta_series):
            r = _safe_div(eq_pv.value, ta_pv.value)
            if r is not None:
                eq_ratio_values.append(PeriodValue(
                    reference_date=eq_pv.reference_date,
                    value=r,
                ))
    eq_ratio_trend = _trend_score(eq_ratio_values) if eq_ratio_values else None

    # ROE stability
    roe_stability = _stability_score(data.get("roe", []))

    score = _avg([eq_ratio_trend, roe_stability])

    return ScoringBlock(
        name="safety",
        score=round(max(0.0, min(1.0, score)), 4),
        components={
            "equity_ratio_trend": eq_ratio_trend,
            "roe_stability": roe_stability,
            "sector_policy": "bank_fallback",
        },
    )


def score_operating_consistency(data: dict[str, list[PeriodValue]]) -> ScoringBlock:
    """Block C: Operating consistency — revenue, EBIT, margins, ROIC trends."""
    rev_trend = _trend_score(data.get("revenue", []))
    ebit_trend = _trend_score(data.get("ebit", []))
    gm_trend = _trend_score(data.get("gross_margin", []))
    em_trend = _trend_score(data.get("ebit_margin", []))
    gm_stability = _stability_score(data.get("gross_margin", []))
    em_stability = _stability_score(data.get("ebit_margin", []))
    roic_trend = _trend_score(data.get("roic", []))

    # Combine margin trends and stability
    margin_score = _avg([gm_trend, em_trend, gm_stability, em_stability])
    score = _avg([rev_trend, ebit_trend, margin_score, roic_trend])

    return ScoringBlock(
        name="operating_consistency",
        score=round(max(0.0, min(1.0, score)), 4),
        components={
            "revenue_trend": rev_trend,
            "ebit_trend": ebit_trend,
            "gross_margin_trend": gm_trend,
            "ebit_margin_trend": em_trend,
            "gross_margin_stability": gm_stability,
            "ebit_margin_stability": em_stability,
            "roic_trend": roic_trend,
        },
    )


def score_capital_discipline(data: dict[str, list[PeriodValue]]) -> ScoringBlock:
    """Block D: Capital discipline — working capital, WC/revenue, capex proxy."""
    # 1. Working capital trend: current_assets - current_liabilities
    ca_series = data.get("current_assets", [])
    cl_series = data.get("current_liabilities", [])
    wc_values: list[PeriodValue] = []
    if ca_series and cl_series:
        for ca_pv, cl_pv in zip(ca_series, cl_series):
            if ca_pv.value is not None and cl_pv.value is not None:
                wc_values.append(PeriodValue(
                    reference_date=ca_pv.reference_date,
                    value=ca_pv.value - cl_pv.value,
                ))
    wc_trend = _trend_score(wc_values) if wc_values else None

    # 2. WC / revenue stability
    rev_series = data.get("revenue", [])
    wc_rev_values: list[PeriodValue] = []
    if wc_values and rev_series:
        for wc_pv, rev_pv in zip(wc_values, rev_series):
            r = _safe_div(wc_pv.value, rev_pv.value)
            if r is not None:
                wc_rev_values.append(PeriodValue(
                    reference_date=wc_pv.reference_date,
                    value=r,
                ))
    wc_rev_stability = _stability_score(wc_rev_values) if wc_rev_values else None

    # 3. Capex proxy: cash_from_investing trend (less negative = improving)
    cfi_trend = _trend_score(data.get("cash_from_investing", []))

    score = _avg([wc_trend, wc_rev_stability, cfi_trend])

    return ScoringBlock(
        name="capital_discipline",
        score=round(max(0.0, min(1.0, score)), 4),
        components={
            "working_capital_trend": wc_trend,
            "wc_revenue_stability": wc_rev_stability,
            "capex_proxy_trend": cfi_trend,
        },
    )
