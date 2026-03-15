"""Face validity — golden set of expected bucket assignments.

A curated list of companies with known economic profiles. After a pipeline run,
check whether the model assigns them to the expected bucket. Mismatches are
flagged as face validity failures.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from q3_quant_engine.thesis.types import Plan2RankingSnapshot, ThesisBucket


@dataclass(frozen=True)
class GoldenCase:
    """A single face-validity expectation."""

    ticker: str
    expected_bucket: ThesisBucket
    rationale: str


@dataclass
class FaceValidityResult:
    """Result of face validity check across all golden cases."""

    total_cases: int
    matched: int
    mismatched: int
    missing: int  # golden case ticker not found in run
    pass_rate: float
    details: list[dict[str, str]] = field(default_factory=list)


# Golden set — canonical expectations for Brazilian market.
# These are sector-level expectations; individual companies may deviate
# if they have unusual profiles. That's what the face validity check detects.

GOLDEN_SET: list[GoldenCase] = [
    # A_DIRECT — pure commodity producers
    GoldenCase("VALE3", ThesisBucket.A_DIRECT, "Mineradora pura — exposicao direta maxima a commodities"),
    GoldenCase("PETR4", ThesisBucket.A_DIRECT, "Petroleo — extracao e refino, exposicao direta forte"),
    GoldenCase("CSNA3", ThesisBucket.A_DIRECT, "Siderurgia — producao de aco, commodity metalica"),
    GoldenCase("GGBR4", ThesisBucket.A_DIRECT, "Siderurgia — Gerdau, exposicao direta a commodities"),
    GoldenCase("SUZB3", ThesisBucket.A_DIRECT, "Papel e celulose — commodity florestal global"),
    GoldenCase("KLBN11", ThesisBucket.A_DIRECT, "Papel e celulose — Klabin"),

    # B_INDIRECT — benefit from commodity cycle without direct production
    GoldenCase("RUMO3", ThesisBucket.B_INDIRECT, "Logistica ferroviaria — transporte de commodities"),
    GoldenCase("CCRO3", ThesisBucket.B_INDIRECT, "Concessoes rodoviarias — infra ligada a fluxo de commodities"),
    GoldenCase("WEGE3", ThesisBucket.B_INDIRECT, "Maquinas e equipamentos — demanda correlacionada"),

    # C_NEUTRAL — low commodity affinity
    GoldenCase("ITUB4", ThesisBucket.C_NEUTRAL, "Banco — sem exposicao direta a commodities"),
    GoldenCase("BBDC4", ThesisBucket.C_NEUTRAL, "Banco — setor financeiro neutro"),
    GoldenCase("RENT3", ThesisBucket.C_NEUTRAL, "Locacao de veiculos — domestico, sem commodity"),
    GoldenCase("RADL3", ThesisBucket.C_NEUTRAL, "Varejo farmaceutico — consumo domestico"),
    GoldenCase("HAPV3", ThesisBucket.C_NEUTRAL, "Saude — planos de saude domesticos"),

    # D_FRAGILE — high dollar/funding fragility
    # Note: D_FRAGILE requires fragility >= 75, which in MVP with defaults is hard to reach.
    # These are aspirational — with rubrics filled, these companies should show high fragility.
    # In MVP with defaults, they may show as C_NEUTRAL instead.
]


def check_face_validity(
    snapshots: list[Plan2RankingSnapshot],
    golden_set: list[GoldenCase] | None = None,
) -> FaceValidityResult:
    """Check face validity of a pipeline run against a golden set.

    Args:
        snapshots: The ranked snapshots from a pipeline run.
        golden_set: Optional override. Defaults to GOLDEN_SET.

    Returns:
        FaceValidityResult with pass rate and per-case details.
    """
    if golden_set is None:
        golden_set = GOLDEN_SET

    snapshot_by_ticker: dict[str, Plan2RankingSnapshot] = {
        s.ticker: s for s in snapshots
    }

    matched = 0
    mismatched = 0
    missing = 0
    details: list[dict[str, str]] = []

    for case in golden_set:
        snap = snapshot_by_ticker.get(case.ticker)

        if snap is None:
            missing += 1
            details.append({
                "ticker": case.ticker,
                "status": "MISSING",
                "expected_bucket": case.expected_bucket.value,
                "actual_bucket": "N/A",
                "rationale": case.rationale,
            })
            continue

        if not snap.eligible:
            mismatched += 1
            details.append({
                "ticker": case.ticker,
                "status": "INELIGIBLE",
                "expected_bucket": case.expected_bucket.value,
                "actual_bucket": "INELIGIBLE",
                "rationale": case.rationale,
            })
            continue

        if snap.bucket == case.expected_bucket:
            matched += 1
            details.append({
                "ticker": case.ticker,
                "status": "MATCH",
                "expected_bucket": case.expected_bucket.value,
                "actual_bucket": snap.bucket.value if snap.bucket else "None",
                "rationale": case.rationale,
            })
        else:
            mismatched += 1
            details.append({
                "ticker": case.ticker,
                "status": "MISMATCH",
                "expected_bucket": case.expected_bucket.value,
                "actual_bucket": snap.bucket.value if snap.bucket else "None",
                "rationale": case.rationale,
            })

    total = len(golden_set)
    pass_rate = matched / total if total > 0 else 0.0

    return FaceValidityResult(
        total_cases=total,
        matched=matched,
        mismatched=mismatched,
        missing=missing,
        pass_rate=round(pass_rate, 3),
        details=details,
    )
