"""Compute NBY_PROXY_FREE from CVM composicao_capital data.

Downloads DFP/ITR composicao_capital CSVs for 2023 and 2024, matches to
issuers by CNPJ, computes net share delta, and persists as computed_metrics
with metric_code='nby_proxy_free'.

Usage:
    cd services/fundamentals-engine
    source .venv/bin/activate
    python scripts/compute_nby_proxy_free.py
"""
from __future__ import annotations

import csv
import io
import logging
import re
import uuid
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx
from sqlalchemy import select, text

from q3_fundamentals_engine.db.session import SessionLocal
from q3_shared_models.entities import (
    ComputedMetric,
    Issuer,
    MetricCode,
    PeriodType,
    Security,
    UniverseClassification,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("nby_proxy_free")

CVM_BASE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC"

SPLIT_RATIO_THRESHOLD = 5.0  # skip if shares ratio > 5x or < 0.2x


@dataclass
class ShareCount:
    reference_date: date
    total_shares: int
    treasury_shares: int
    net_shares: int
    source_file: str


def _normalize_cnpj(cnpj: str) -> str:
    return re.sub(r"[^0-9]", "", cnpj)


def _download_composicao_capital(doc_type: str, year: int) -> list[dict[str, str]]:
    """Download composicao_capital CSV from CVM zip."""
    url = f"{CVM_BASE}/{doc_type}/DADOS/{doc_type.lower()}_cia_aberta_{year}.zip"
    logger.info("Downloading %s %d from %s", doc_type, year, url)
    resp = httpx.get(url, timeout=120, verify=False, follow_redirects=True)
    resp.raise_for_status()

    z = zipfile.ZipFile(io.BytesIO(resp.content))
    for name in z.namelist():
        if "composicao_capital" in name.lower():
            with z.open(name) as f:
                data = f.read().decode("latin-1")
                reader = csv.DictReader(io.StringIO(data), delimiter=";")
                rows = list(reader)
                logger.info("  %s: %d rows", name, len(rows))
                return rows
    return []


def _build_share_counts(
    rows: list[dict[str, str]], source_file: str
) -> dict[str, list[ShareCount]]:
    """Build CNPJ → list of ShareCount from composicao_capital rows."""
    result: dict[str, list[ShareCount]] = defaultdict(list)
    for row in rows:
        cnpj = _normalize_cnpj(row.get("CNPJ_CIA", ""))
        if not cnpj:
            continue
        try:
            ref_date = date.fromisoformat(row["DT_REFER"])
            total = int(row.get("QT_ACAO_TOTAL_CAP_INTEGR", "0") or "0")
            treasury = int(row.get("QT_ACAO_TOTAL_TESOURO", "0") or "0")
        except (ValueError, KeyError):
            continue
        if total <= 0:
            continue
        net = total - treasury
        result[cnpj].append(ShareCount(
            reference_date=ref_date,
            total_shares=total,
            treasury_shares=treasury,
            net_shares=net,
            source_file=source_file,
        ))
    return result


def _snap_to_quarter_end(d: date) -> date:
    month = d.month
    if month <= 3:
        return date(d.year, 3, 31)
    elif month <= 6:
        return date(d.year, 6, 30)
    elif month <= 9:
        return date(d.year, 9, 30)
    else:
        return date(d.year, 12, 31)


def _find_closest(counts: list[ShareCount], target: date, max_days: int = 45) -> ShareCount | None:
    """Find the ShareCount closest to target within max_days."""
    best = None
    best_dist = max_days + 1
    for sc in counts:
        dist = abs((sc.reference_date - target).days)
        if dist < best_dist:
            best = sc
            best_dist = dist
    return best


def main() -> None:
    # 1. Download all composicao_capital data
    all_share_data: dict[str, list[ShareCount]] = defaultdict(list)

    for doc_type, year in [("DFP", 2023), ("ITR", 2023), ("DFP", 2024), ("ITR", 2024)]:
        rows = _download_composicao_capital(doc_type, year)
        source = f"CVM_{doc_type}_{year}_composicao_capital"
        counts = _build_share_counts(rows, source)
        for cnpj, scs in counts.items():
            all_share_data[cnpj].extend(scs)

    logger.info("Total companies with share data: %d", len(all_share_data))

    # 2. Match to CORE_ELIGIBLE issuers and compute NBY_PROXY_FREE
    with SessionLocal() as session:
        core_issuers = session.execute(
            select(Issuer.id, Issuer.cnpj, Issuer.cvm_code, Issuer.legal_name)
            .join(UniverseClassification, UniverseClassification.issuer_id == Issuer.id)
            .join(Security, Security.issuer_id == Issuer.id)
            .where(
                UniverseClassification.universe_class == "CORE_ELIGIBLE",
                UniverseClassification.superseded_at.is_(None),
                Security.is_primary.is_(True),
                Security.valid_to.is_(None),
            )
        ).all()

        logger.info("CORE_ELIGIBLE issuers: %d", len(core_issuers))

        computed = 0
        skipped_no_data = 0
        skipped_no_t = 0
        skipped_no_t4 = 0
        skipped_split = 0
        skipped_already = 0

        # Use as_of = latest available quarter-end
        as_of = date(2024, 12, 31)
        t4_target = date(2023, 12, 31)

        for issuer_id, cnpj, cvm_code, legal_name in core_issuers:
            counts = all_share_data.get(cnpj, [])
            if not counts:
                skipped_no_data += 1
                continue

            # Find shares at t and t-4
            sc_t = _find_closest(counts, as_of)
            sc_t4 = _find_closest(counts, t4_target)

            if sc_t is None:
                skipped_no_t += 1
                continue
            if sc_t4 is None:
                skipped_no_t4 += 1
                continue
            if sc_t4.net_shares <= 0:
                skipped_no_t4 += 1
                continue

            # Sanity check: split detection
            ratio = sc_t.net_shares / sc_t4.net_shares
            if ratio > SPLIT_RATIO_THRESHOLD or ratio < (1 / SPLIT_RATIO_THRESHOLD):
                logger.warning(
                    "Split detected for %s (%s): ratio=%.2f, skipping",
                    cvm_code, legal_name[:30], ratio,
                )
                skipped_split += 1
                continue

            nby_proxy = (sc_t4.net_shares - sc_t.net_shares) / sc_t4.net_shares

            inputs = {
                "source": "CVM_composicao_capital",
                "method": "share_count_delta_cvm_composicao",
                "shares_t": sc_t.net_shares,
                "shares_t_total": sc_t.total_shares,
                "shares_t_treasury": sc_t.treasury_shares,
                "shares_t_date": str(sc_t.reference_date),
                "shares_t_source": sc_t.source_file,
                "shares_t4": sc_t4.net_shares,
                "shares_t4_total": sc_t4.total_shares,
                "shares_t4_treasury": sc_t4.treasury_shares,
                "shares_t4_date": str(sc_t4.reference_date),
                "shares_t4_source": sc_t4.source_file,
                "nby_proxy_free": nby_proxy,
                "share_ratio_t_over_t4": round(ratio, 6),
            }

            # Upsert
            existing = session.execute(
                select(ComputedMetric)
                .where(
                    ComputedMetric.issuer_id == issuer_id,
                    ComputedMetric.metric_code == MetricCode.nby_proxy_free,
                    ComputedMetric.period_type == PeriodType.annual,
                    ComputedMetric.reference_date == as_of,
                )
                .with_for_update()
            ).scalar_one_or_none()

            if existing is not None:
                existing.value = nby_proxy
                existing.formula_version = 1
                existing.inputs_snapshot_json = inputs
                existing.source_filing_ids_json = []
            else:
                session.add(ComputedMetric(
                    id=uuid.uuid4(),
                    issuer_id=issuer_id,
                    metric_code=MetricCode.nby_proxy_free,
                    period_type=PeriodType.annual,
                    reference_date=as_of,
                    value=nby_proxy,
                    formula_version=1,
                    inputs_snapshot_json=inputs,
                    source_filing_ids_json=[],
                ))
            computed += 1

        session.commit()
        logger.info("NBY_PROXY_FREE: computed=%d, skipped_no_data=%d, skipped_no_t=%d, skipped_no_t4=%d, skipped_split=%d",
                     computed, skipped_no_data, skipped_no_t, skipped_no_t4, skipped_split)

        # --- Phase 2: Compose NPY_PROXY_FREE = DY + NBY_PROXY_FREE ---
        logger.info("Computing NPY_PROXY_FREE...")
        npy_computed = 0
        npy_null = 0

        # Load all DY and NBY_PROXY_FREE for Core issuers at as_of
        dy_metrics = {
            row[0]: float(row[1])
            for row in session.execute(text(f"""
                SELECT cm.issuer_id, cm.value
                FROM computed_metrics cm
                JOIN universe_classifications uc ON uc.issuer_id = cm.issuer_id
                    AND uc.universe_class = 'CORE_ELIGIBLE' AND uc.superseded_at IS NULL
                JOIN securities s ON s.issuer_id = cm.issuer_id AND s.is_primary = true AND s.valid_to IS NULL
                WHERE cm.metric_code = 'dividend_yield'
                  AND cm.reference_date = '{as_of}'
            """)).fetchall()
            if row[1] is not None
        }

        nby_proxy_metrics = {
            row[0]: float(row[1])
            for row in session.execute(text(f"""
                SELECT cm.issuer_id, cm.value
                FROM computed_metrics cm
                WHERE cm.metric_code = 'nby_proxy_free'
                  AND cm.reference_date = '{as_of}'
            """)).fetchall()
            if row[1] is not None
        }

        for issuer_id, cnpj, cvm_code, legal_name in core_issuers:
            dy_val = dy_metrics.get(issuer_id)
            nby_val = nby_proxy_metrics.get(issuer_id)

            if dy_val is None or nby_val is None:
                npy_null += 1
                continue

            npy_val = dy_val + nby_val

            npy_inputs = {
                "dividend_yield": dy_val,
                "nby_proxy_free": nby_val,
                "npy_proxy_free": npy_val,
                "formula": "dy + nby_proxy_free",
                "formula_version": 1,
                "reference_date": str(as_of),
                "trail": "free-source",
            }

            existing = session.execute(
                select(ComputedMetric)
                .where(
                    ComputedMetric.issuer_id == issuer_id,
                    ComputedMetric.metric_code == MetricCode.npy_proxy_free,
                    ComputedMetric.period_type == PeriodType.annual,
                    ComputedMetric.reference_date == as_of,
                )
                .with_for_update()
            ).scalar_one_or_none()

            if existing is not None:
                existing.value = npy_val
                existing.formula_version = 1
                existing.inputs_snapshot_json = npy_inputs
                existing.source_filing_ids_json = []
            else:
                session.add(ComputedMetric(
                    id=uuid.uuid4(),
                    issuer_id=issuer_id,
                    metric_code=MetricCode.npy_proxy_free,
                    period_type=PeriodType.annual,
                    reference_date=as_of,
                    value=npy_val,
                    formula_version=1,
                    inputs_snapshot_json=npy_inputs,
                    source_filing_ids_json=[],
                ))
            npy_computed += 1

        session.commit()
        logger.info("NPY_PROXY_FREE: computed=%d, null=%d", npy_computed, npy_null)

        # --- Report ---
        print(f"\n{'=' * 60}")
        print("Free-Source Trail Report")
        print(f"{'=' * 60}")
        print(f"CORE issuers: {len(core_issuers)}")
        print()
        print("NBY_PROXY_FREE:")
        print(f"  Computed:  {computed}")
        print(f"  Skipped:   no_data={skipped_no_data} no_t={skipped_no_t} no_t4={skipped_no_t4} split={skipped_split}")
        print()
        print("NPY_PROXY_FREE:")
        print(f"  Computed:  {npy_computed}")
        print(f"  NULL (missing DY or NBY_PROXY): {npy_null}")
        print()

        # Coverage
        denom = 232
        for metric in ["dividend_yield", "nby_proxy_free", "npy_proxy_free", "net_buyback_yield", "net_payout_yield"]:
            count = session.execute(text(f"""
                SELECT count(DISTINCT cm.issuer_id)
                FROM computed_metrics cm
                JOIN universe_classifications uc ON uc.issuer_id = cm.issuer_id
                    AND uc.universe_class = 'CORE_ELIGIBLE' AND uc.superseded_at IS NULL
                JOIN securities s ON s.issuer_id = cm.issuer_id AND s.is_primary = true AND s.valid_to IS NULL
                WHERE cm.metric_code = '{metric}'
            """)).scalar()
            trail = "free" if "proxy" in metric else "exact"
            print(f"  {metric:25s}: {count}/{denom} = {count/denom*100:.1f}%  [{trail}]")
        print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
