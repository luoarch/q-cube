"""Plan 2 pipeline runner — end-to-end orchestration for a single run.

Flow: create plan2_run → for each issuer: eligibility → F1 draft → B2 complete
→ A scoring → snapshot → sort/rank → persist plan2_thesis_scores → update plan2_run.

This module owns persistence. It does NOT own scoring, feature extraction, or
input assembly — it delegates to MF-A, MF-F1, and B2 input_assembly respectively.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from q3_shared_models.entities import (
    ComputedMetric,
    Issuer,
    MetricCode,
    PeriodType,
    Plan2Run,
    Plan2ThesisScore,
    StatementLine,
)
from q3_quant_engine.thesis.config import THESIS_CONFIG_VERSION
from q3_quant_engine.thesis.eligibility import check_base_eligibility
from q3_quant_engine.thesis.features.draft_builder import (
    IssuerFeatureData,
    build_feature_draft,
)
from q3_quant_engine.thesis.input_assembly import complete_feature_input
from q3_quant_engine.thesis.scoring import (
    assign_thesis_bucket,
    compute_final_commodity_affinity_score,
    compute_final_dollar_fragility_score,
    compute_thesis_rank_score,
    generate_explanation,
    sort_plan2_rank,
)
from q3_quant_engine.thesis.types import (
    BaseEligibility,
    FragilityVector,
    OpportunityVector,
    Plan2FeatureInput,
    Plan2RankingSnapshot,
    ScoreProvenance,
)

logger = logging.getLogger(__name__)

PIPELINE_VERSION = "1.0.0"


def _provenance_to_dict(prov: dict[str, ScoreProvenance]) -> dict[str, dict]:
    return {k: asdict(v) for k, v in prov.items()}


def _get_latest_metric(
    session: Session,
    issuer_id: uuid.UUID,
    metric_code: MetricCode,
) -> float | None:
    """Get the most recent annual computed metric value for an issuer."""
    row = session.execute(
        select(ComputedMetric.value)
        .where(
            ComputedMetric.issuer_id == issuer_id,
            ComputedMetric.metric_code == metric_code.value,
            ComputedMetric.period_type == PeriodType.annual,
        )
        .order_by(ComputedMetric.reference_date.desc())
        .limit(1)
    ).scalar_one_or_none()
    return float(row) if row is not None else None


def _get_latest_statement_values_for_issuer(
    session: Session,
    issuer_id: uuid.UUID,
    canonical_keys: list[str],
) -> dict[str, float | None]:
    """Get the most recent annual statement line values for an issuer.

    Uses the issuer's filings to scope the query.
    """
    from q3_shared_models.entities import Filing

    # Get latest filing for issuer
    latest_filing_id = session.execute(
        select(Filing.id)
        .where(Filing.issuer_id == issuer_id)
        .order_by(Filing.reference_date.desc())
        .limit(1)
    ).scalar_one_or_none()

    result: dict[str, float | None] = {k: None for k in canonical_keys}
    if latest_filing_id is None:
        return result

    rows = session.execute(
        select(StatementLine.canonical_key, StatementLine.normalized_value)
        .where(
            StatementLine.filing_id == latest_filing_id,
            StatementLine.canonical_key.in_(canonical_keys),
            StatementLine.period_type == PeriodType.annual,
        )
    ).all()

    for row in rows:
        if row[0] is not None and row[1] is not None:
            result[row[0]] = float(row[1])

    return result

def _build_issuer_feature_data(
    session: Session,
    issuer: Issuer,
    core_rank_percentile: float,
    has_valid_financials: bool,
) -> IssuerFeatureData:
    """Assemble IssuerFeatureData from DB for a single issuer."""
    issuer_uuid = issuer.id

    debt_to_ebitda = _get_latest_metric(session, issuer_uuid, MetricCode.debt_to_ebitda)
    interest_coverage = _get_latest_metric(session, issuer_uuid, MetricCode.interest_coverage)

    stmt_values = _get_latest_statement_values_for_issuer(
        session, issuer_uuid, ["short_term_debt", "long_term_debt"],
    )

    return IssuerFeatureData(
        issuer_id=str(issuer_uuid),
        ticker=_issuer_ticker(issuer),
        sector=issuer.sector,
        subsector=issuer.subsector,
        passed_core_screening=True,  # all issuers in universe passed core
        has_valid_financials=has_valid_financials,
        interest_coverage=interest_coverage,
        debt_to_ebitda=debt_to_ebitda,
        core_rank_percentile=core_rank_percentile,
        short_term_debt=stmt_values.get("short_term_debt"),
        long_term_debt=stmt_values.get("long_term_debt"),
    )


def _issuer_ticker(issuer: Issuer, session: Session | None = None) -> str:
    """Get primary ticker for issuer. Falls back to cvm_code.

    If securities aren't loaded on the issuer, queries directly.
    """
    # Try loaded relationship first
    if hasattr(issuer, "securities") and issuer.securities:
        for sec in issuer.securities:
            if getattr(sec, "is_primary", False):
                return sec.ticker

    # Fallback: direct query
    if session is not None:
        from q3_shared_models.entities import Security
        ticker = session.execute(
            select(Security.ticker)
            .where(Security.issuer_id == issuer.id, Security.is_primary.is_(True))
            .limit(1)
        ).scalar_one_or_none()
        if ticker:
            return ticker

    return issuer.cvm_code


def _score_eligible_issuer(
    feature_input: Plan2FeatureInput,
    eligibility: BaseEligibility,
    company_name: str,
    sector: str | None,
) -> Plan2RankingSnapshot:
    """Run MF-A scoring on an eligible issuer and return a snapshot."""
    # Opportunity
    commodity_affinity = compute_final_commodity_affinity_score(
        feature_input.direct_commodity_exposure_score,
        feature_input.indirect_commodity_exposure_score,
        feature_input.export_fx_leverage_score,
    )
    # Fragility
    fragility = compute_final_dollar_fragility_score(
        feature_input.refinancing_stress_score,
        feature_input.usd_debt_exposure_score,
        feature_input.usd_import_dependence_score,
        feature_input.usd_revenue_offset_score,
    )
    # Bucket
    bucket = assign_thesis_bucket(
        feature_input.direct_commodity_exposure_score,
        feature_input.indirect_commodity_exposure_score,
        fragility,
    )
    # Rank score
    rank_score = compute_thesis_rank_score(
        commodity_affinity, fragility, feature_input.core_rank_percentile,
    )
    # Explanation
    explanation = generate_explanation(
        ticker=feature_input.ticker,
        bucket=bucket,
        thesis_rank_score=rank_score,
        commodity_affinity=commodity_affinity,
        fragility=fragility,
        base_core=feature_input.core_rank_percentile,
        direct_commodity=feature_input.direct_commodity_exposure_score,
        indirect_commodity=feature_input.indirect_commodity_exposure_score,
        export_fx=feature_input.export_fx_leverage_score,
        refinancing_stress=feature_input.refinancing_stress_score,
        usd_debt=feature_input.usd_debt_exposure_score,
        usd_import=feature_input.usd_import_dependence_score,
        usd_revenue_offset=feature_input.usd_revenue_offset_score,
    )

    return Plan2RankingSnapshot(
        issuer_id=feature_input.issuer_id,
        ticker=feature_input.ticker,
        company_name=company_name,
        sector=sector,
        eligible=True,
        eligibility=eligibility,
        opportunity_vector=OpportunityVector(
            direct_commodity_exposure_score=feature_input.direct_commodity_exposure_score,
            indirect_commodity_exposure_score=feature_input.indirect_commodity_exposure_score,
            export_fx_leverage_score=feature_input.export_fx_leverage_score,
            final_commodity_affinity_score=commodity_affinity,
        ),
        fragility_vector=FragilityVector(
            refinancing_stress_score=feature_input.refinancing_stress_score,
            usd_debt_exposure_score=feature_input.usd_debt_exposure_score,
            usd_import_dependence_score=feature_input.usd_import_dependence_score,
            usd_revenue_offset_score=feature_input.usd_revenue_offset_score,
            final_dollar_fragility_score=fragility,
        ),
        bucket=bucket,
        thesis_rank_score=rank_score,
        base_core_score=feature_input.core_rank_percentile,
        explanation=explanation,
        provenance=feature_input.provenance,
    )


def _make_ineligible_snapshot(
    issuer_id: str,
    ticker: str,
    company_name: str,
    sector: str | None,
    eligibility: BaseEligibility,
) -> Plan2RankingSnapshot:
    return Plan2RankingSnapshot(
        issuer_id=issuer_id,
        ticker=ticker,
        company_name=company_name,
        sector=sector,
        eligible=False,
        eligibility=eligibility,
    )


def _persist_thesis_score(
    session: Session,
    plan2_run_id: uuid.UUID,
    snapshot: Plan2RankingSnapshot,
    feature_input_json: dict,
) -> Plan2ThesisScore:
    """Create and add a Plan2ThesisScore record to the session."""
    explanation_json = asdict(snapshot.explanation) if snapshot.explanation else None

    score = Plan2ThesisScore(
        id=uuid.uuid4(),
        plan2_run_id=plan2_run_id,
        issuer_id=uuid.UUID(snapshot.issuer_id),
        eligible=snapshot.eligible,
        eligibility_json=asdict(snapshot.eligibility),
        # opportunity vector
        direct_commodity_exposure_score=(
            snapshot.opportunity_vector.direct_commodity_exposure_score
            if snapshot.opportunity_vector else None
        ),
        indirect_commodity_exposure_score=(
            snapshot.opportunity_vector.indirect_commodity_exposure_score
            if snapshot.opportunity_vector else None
        ),
        export_fx_leverage_score=(
            snapshot.opportunity_vector.export_fx_leverage_score
            if snapshot.opportunity_vector else None
        ),
        final_commodity_affinity_score=(
            snapshot.opportunity_vector.final_commodity_affinity_score
            if snapshot.opportunity_vector else None
        ),
        # fragility vector
        refinancing_stress_score=(
            snapshot.fragility_vector.refinancing_stress_score
            if snapshot.fragility_vector else None
        ),
        usd_debt_exposure_score=(
            snapshot.fragility_vector.usd_debt_exposure_score
            if snapshot.fragility_vector else None
        ),
        usd_import_dependence_score=(
            snapshot.fragility_vector.usd_import_dependence_score
            if snapshot.fragility_vector else None
        ),
        usd_revenue_offset_score=(
            snapshot.fragility_vector.usd_revenue_offset_score
            if snapshot.fragility_vector else None
        ),
        final_dollar_fragility_score=(
            snapshot.fragility_vector.final_dollar_fragility_score
            if snapshot.fragility_vector else None
        ),
        # ranking
        bucket=snapshot.bucket.value if snapshot.bucket else None,
        thesis_rank_score=snapshot.thesis_rank_score,
        thesis_rank=snapshot.thesis_rank,
        # provenance
        feature_input_json=feature_input_json,
        explanation_json=explanation_json,
    )
    session.add(score)
    return score


def run_plan2_pipeline(
    session: Session,
    strategy_run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    issuer_universe: list[tuple[Issuer, float, bool]],
    as_of_date: date | None = None,
) -> Plan2Run:
    """Execute full Plan 2 pipeline for a list of issuers.

    Args:
        session: SQLAlchemy session (caller manages transaction).
        strategy_run_id: The parent strategy run this plan2 run belongs to.
        tenant_id: Tenant scope.
        issuer_universe: List of (issuer, core_rank_percentile, has_valid_financials).
        as_of_date: Optional date override. Defaults to today.

    Returns:
        The Plan2Run record with status completed or failed.
    """
    if as_of_date is None:
        as_of_date = date.today()

    as_of_str = as_of_date.isoformat()

    # Create plan2_run record
    plan2_run = Plan2Run(
        id=uuid.uuid4(),
        strategy_run_id=strategy_run_id,
        tenant_id=tenant_id,
        thesis_config_version=THESIS_CONFIG_VERSION,
        pipeline_version=PIPELINE_VERSION,
        as_of_date=as_of_date,
        status="running",
        started_at=datetime.now(UTC),
    )
    session.add(plan2_run)
    session.flush()  # get the id assigned

    snapshots: list[Plan2RankingSnapshot] = []
    feature_inputs: dict[str, dict] = {}  # issuer_id → feature_input_json
    total_eligible = 0
    total_ineligible = 0

    for issuer, core_rank_percentile, has_valid_financials in issuer_universe:
        issuer_id_str = str(issuer.id)
        ticker = _issuer_ticker(issuer, session)
        company_name = issuer.trade_name or issuer.legal_name

        # 1. Build feature data from DB
        feature_data = _build_issuer_feature_data(
            session, issuer, core_rank_percentile, has_valid_financials,
        )

        # 2. F1: build partial draft
        draft = build_feature_draft(feature_data, as_of_str)

        # 3. Eligibility check
        eligibility = check_base_eligibility(
            passed_core_screening=draft.passed_core_screening,
            has_valid_financials=draft.has_valid_financials,
            interest_coverage=draft.interest_coverage,
            debt_to_ebitda=draft.debt_to_ebitda,
        )

        if not eligibility.eligible_for_plan2:
            total_ineligible += 1
            snapshot = _make_ineligible_snapshot(
                issuer_id_str, ticker, company_name, issuer.sector, eligibility,
            )
            snapshots.append(snapshot)
            feature_inputs[issuer_id_str] = {
                "draft": asdict(draft),
                "provenance": _provenance_to_dict(draft.provenance),
            }
            continue

        # 4. B2: complete draft → input
        feature_input = complete_feature_input(draft, as_of_str)

        # 5. A: score eligible issuer
        snapshot = _score_eligible_issuer(
            feature_input, eligibility, company_name, issuer.sector,
        )
        snapshots.append(snapshot)
        total_eligible += 1

        feature_inputs[issuer_id_str] = {
            "input": asdict(feature_input),
            "provenance": _provenance_to_dict(feature_input.provenance),
        }

    # 6. Sort and assign thesis_rank
    sorted_snapshots = sort_plan2_rank(snapshots)

    # 7. Persist thesis scores
    for snapshot in sorted_snapshots:
        _persist_thesis_score(
            session,
            plan2_run.id,
            snapshot,
            feature_inputs.get(snapshot.issuer_id, {}),
        )

    # 8. Update plan2_run metadata
    bucket_dist: dict[str, int] = {}
    for s in sorted_snapshots:
        if s.bucket is not None:
            key = s.bucket.value
            bucket_dist[key] = bucket_dist.get(key, 0) + 1

    plan2_run.total_eligible = total_eligible
    plan2_run.total_ineligible = total_ineligible
    plan2_run.bucket_distribution_json = bucket_dist
    plan2_run.status = "completed"
    plan2_run.completed_at = datetime.now(UTC)

    session.flush()

    logger.info(
        "plan2 run=%s completed: eligible=%d ineligible=%d buckets=%s",
        plan2_run.id, total_eligible, total_ineligible, bucket_dist,
    )

    return plan2_run
