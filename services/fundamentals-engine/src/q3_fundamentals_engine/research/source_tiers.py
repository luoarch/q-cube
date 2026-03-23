"""Source tier derivation rules for NPY research panel.

Tier hierarchy:
    A = Official (CVM filings)
    B = Trusted market source (Yahoo/brapi provider data)
    C = Derived (internally computed, e.g. market_cap = price * shares)
    D = Missing / not computable

Rules are deterministic and centralized here — no ad-hoc tier assignment elsewhere.
"""

from __future__ import annotations

from enum import Enum


class SourceTier(str, Enum):
    A = "A"  # Official (CVM)
    B = "B"  # Trusted market source (provider)
    C = "C"  # Derived (internally computed)
    D = "D"  # Missing / not computable


def worst_tier(*tiers: SourceTier) -> SourceTier:
    """Return the worst (lowest quality) tier from the given tiers.

    D > C > B > A (D is worst).
    """
    _ORDER = {SourceTier.A: 0, SourceTier.B: 1, SourceTier.C: 2, SourceTier.D: 3}
    return max(tiers, key=lambda t: _ORDER[t])


def derive_dy_tiers(
    inputs_snapshot: dict | None,
    source_filing_ids: list | None,
) -> tuple[SourceTier, SourceTier]:
    """Derive (distributions_tier, market_cap_tier) for a DY metric.

    Returns:
        (dy_source_tier, market_cap_source_tier)

    Rules:
        - Distributions come from CVM filings → A if filing IDs present, else D.
        - Market_cap comes from provider snapshot → B.
          (If market_cap were derived from price*shares, it would be C,
           but current pipeline always uses provider market_cap.)
    """
    if inputs_snapshot is None:
        return SourceTier.D, SourceTier.D

    # Distributions tier: A if backed by CVM filings
    has_filings = bool(source_filing_ids)
    distributions_tier = SourceTier.A if has_filings else SourceTier.D

    # Market cap tier: B if present from provider
    market_cap = inputs_snapshot.get("market_cap")
    if market_cap is not None and market_cap > 0:
        market_cap_tier = SourceTier.B
    else:
        market_cap_tier = SourceTier.D

    dy_tier = worst_tier(distributions_tier, market_cap_tier)
    return dy_tier, market_cap_tier


def derive_nby_tiers(
    inputs_snapshot: dict | None,
) -> tuple[SourceTier, SourceTier]:
    """Derive (nby_source_tier, shares_source_tier) for an NBY metric.

    Returns:
        (nby_source_tier, shares_source_tier)

    Rules:
        - shares_outstanding at t and t-4 come from provider snapshots → B.
        - If either is missing → D.
    """
    if inputs_snapshot is None:
        return SourceTier.D, SourceTier.D

    shares_t = inputs_snapshot.get("shares_t")
    shares_t4 = inputs_snapshot.get("shares_t4")

    if shares_t is not None and shares_t4 is not None:
        shares_tier = SourceTier.B
    else:
        shares_tier = SourceTier.D

    return shares_tier, shares_tier


def derive_npy_tier(
    dy_tier: SourceTier,
    nby_tier: SourceTier,
) -> SourceTier:
    """NPY tier = worst of DY and NBY tiers."""
    return worst_tier(dy_tier, nby_tier)
