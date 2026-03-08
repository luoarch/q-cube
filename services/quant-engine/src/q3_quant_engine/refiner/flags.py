"""Refiner flag detection — red flags and strength flags."""

from __future__ import annotations

from q3_quant_engine.refiner.types import Flag, PeriodValue


def _values(series: list[PeriodValue]) -> list[float]:
    return [pv.value for pv in series if pv.value is not None]


def _latest(series: list[PeriodValue]) -> float | None:
    if not series:
        return None
    return series[-1].value


def detect_flags(data: dict[str, list[PeriodValue]], classification: str) -> list[Flag]:
    flags: list[Flag] = []

    cfo = data.get("cash_from_operations", [])
    ni = data.get("net_income", [])
    ebit = data.get("ebit", [])
    gm = data.get("gross_margin", [])
    em = data.get("ebit_margin", [])
    nd = data.get("net_debt", [])
    dte = data.get("debt_to_ebitda", [])
    fr = data.get("financial_result", [])
    ca = data.get("current_assets", [])
    cl = data.get("current_liabilities", [])
    cfi = data.get("cash_from_investing", [])
    cc = data.get("cash_conversion", [])
    rev = data.get("revenue", [])

    # --- Red flags ---

    # Earnings-CFO divergence: NI positive but CFO negative (latest period)
    if _latest(ni) is not None and _latest(cfo) is not None:
        if _latest(ni) > 0 and _latest(cfo) < 0:  # type: ignore[operator]
            flags.append(Flag("earnings_cfo_divergence", "red", "Net income positive but operating cash flow negative"))

    # EBIT deterioration: 2 consecutive declines
    ebit_vals = _values(ebit)
    if len(ebit_vals) >= 3 and ebit_vals[-1] < ebit_vals[-2] < ebit_vals[-3]:
        flags.append(Flag("ebit_deterioration", "red", "EBIT declining for 3 consecutive periods"))

    # Margin compression: gross or EBIT margin falling
    gm_vals = _values(gm)
    if len(gm_vals) >= 3 and gm_vals[-1] < gm_vals[-2] < gm_vals[-3]:
        flags.append(Flag("margin_compression", "red", "Gross margin declining for 3 consecutive periods"))

    em_vals = _values(em)
    if len(em_vals) >= 3 and em_vals[-1] < em_vals[-2] < em_vals[-3]:
        if not any(f.code == "margin_compression" for f in flags):
            flags.append(Flag("margin_compression", "red", "EBIT margin declining for 3 consecutive periods"))

    # Leverage rising (non-financial only)
    if classification == "non_financial":
        nd_vals = _values(nd)
        if len(nd_vals) >= 2 and nd_vals[-1] > nd_vals[-2]:
            flags.append(Flag("leverage_rising", "red", "Net debt increasing"))

    # Debt/EBITDA worsening
    if classification not in ("bank", "insurer", "holding"):
        dte_vals = _values(dte)
        if len(dte_vals) >= 2 and dte_vals[-1] > dte_vals[-2]:
            latest_dte = dte_vals[-1]
            if latest_dte > 3.0:
                flags.append(Flag("debt_ebitda_worsening", "red", f"Debt/EBITDA rising and above 3x ({latest_dte:.1f}x)"))

    # Weak interest coverage
    if classification not in ("bank", "insurer", "holding") and ebit and fr:
        latest_ebit = _latest(ebit)
        latest_fr = _latest(fr)
        if latest_ebit is not None and latest_fr is not None and latest_fr != 0:
            ic = latest_ebit / abs(latest_fr)
            if ic < 1.5:
                flags.append(Flag("weak_interest_coverage", "red", f"Interest coverage below 1.5x ({ic:.1f}x)"))

    # Working capital deterioration
    if ca and cl:
        latest_ca = _latest(ca)
        latest_cl = _latest(cl)
        if latest_ca is not None and latest_cl is not None:
            wc_now = latest_ca - latest_cl
            if len(_values(ca)) >= 2 and len(_values(cl)) >= 2:
                prev_ca = _values(ca)[-2]
                prev_cl = _values(cl)[-2]
                wc_prev = prev_ca - prev_cl
                if wc_now < wc_prev and wc_now < 0:
                    flags.append(Flag("working_capital_deterioration", "red", "Working capital negative and declining"))

    # Negative FCF recurring
    if cfo and cfi:
        fcf_count_negative = 0
        for cfo_pv, cfi_pv in zip(cfo, cfi):
            if cfo_pv.value is not None and cfi_pv.value is not None:
                if cfo_pv.value + cfi_pv.value < 0:
                    fcf_count_negative += 1
        total_periods = min(len(_values(cfo)), len(_values(cfi)))
        if total_periods >= 2 and fcf_count_negative >= 2:
            flags.append(Flag("negative_fcf_recurring", "red", f"Negative free cash flow in {fcf_count_negative} of {total_periods} periods"))

    # --- Strength flags ---

    # EBIT growing
    if len(ebit_vals) >= 2 and ebit_vals[-1] > ebit_vals[-2]:
        if len(ebit_vals) < 3 or ebit_vals[-2] >= ebit_vals[-3]:
            flags.append(Flag("ebit_growing", "strength", "EBIT growing"))

    # Margin resilient: low stdev relative to mean
    if len(gm_vals) >= 3:
        import statistics
        mean_gm = statistics.mean(gm_vals)
        if mean_gm > 0:
            cv = statistics.stdev(gm_vals) / mean_gm
            if cv < 0.1:
                flags.append(Flag("margin_resilient", "strength", "Gross margin highly stable"))

    # Deleveraging
    if classification not in ("bank", "insurer", "holding"):
        nd_vals = _values(nd)
        if len(nd_vals) >= 2 and nd_vals[-1] < nd_vals[-2]:
            flags.append(Flag("deleveraging", "strength", "Net debt decreasing"))

    # Strong cash conversion
    cc_vals = _values(cc)
    if cc_vals and cc_vals[-1] > 1.0:
        flags.append(Flag("strong_cash_conversion", "strength", "Cash conversion above 100%"))

    # Consistent FCF
    if cfo and cfi:
        fcf_count_positive = 0
        total_periods = min(len(_values(cfo)), len(_values(cfi)))
        for cfo_pv, cfi_pv in zip(cfo, cfi):
            if cfo_pv.value is not None and cfi_pv.value is not None:
                if cfo_pv.value + cfi_pv.value > 0:
                    fcf_count_positive += 1
        if total_periods >= 3 and fcf_count_positive == total_periods:
            flags.append(Flag("consistent_fcf", "strength", "Positive FCF in all periods"))

    # Disciplined working capital
    if ca and cl and rev:
        wc_rev_vals: list[float] = []
        for ca_pv, cl_pv, rev_pv in zip(ca, cl, rev):
            if all(pv.value is not None for pv in [ca_pv, cl_pv, rev_pv]) and rev_pv.value != 0:
                wc = ca_pv.value - cl_pv.value  # type: ignore[operator]
                wc_rev_vals.append(wc / rev_pv.value)  # type: ignore[operator]
        if len(wc_rev_vals) >= 3:
            import statistics
            cv = abs(statistics.stdev(wc_rev_vals) / statistics.mean(wc_rev_vals)) if statistics.mean(wc_rev_vals) != 0 else 999
            if cv < 0.15:
                flags.append(Flag("disciplined_working_capital", "strength", "Working capital/revenue ratio stable"))

    # Strong operating consistency
    rev_vals = _values(rev)
    if len(rev_vals) >= 3 and len(ebit_vals) >= 3:
        rev_growing = all(b > a for a, b in zip(rev_vals, rev_vals[1:]))
        ebit_growing = all(b > a for a, b in zip(ebit_vals, ebit_vals[1:]))
        if rev_growing and ebit_growing:
            flags.append(Flag("strong_operating_consistency", "strength", "Revenue and EBIT growing every period"))

    return flags
