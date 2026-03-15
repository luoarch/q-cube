"""Tests for Plan 2 internal API router.

Uses FastAPI TestClient with mocked DB session.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, UTC
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from q3_quant_engine.thesis.router import router, _get_db


# =====================================================================
# Test app setup
# =====================================================================


def _create_test_app(mock_session: MagicMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    def _override_db():  # type: ignore[no-untyped-def]
        yield mock_session

    app.dependency_overrides[_get_db] = _override_db
    return TestClient(app)


# =====================================================================
# Mock data factories
# =====================================================================


def _mock_plan2_run(
    run_id: uuid.UUID | None = None,
    status: str = "completed",
    total_eligible: int = 5,
    total_ineligible: int = 2,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=run_id or uuid.uuid4(),
        strategy_run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        thesis_config_version="1.0.0",
        pipeline_version="1.0.0",
        as_of_date=date(2026, 3, 15),
        total_eligible=total_eligible,
        total_ineligible=total_ineligible,
        bucket_distribution_json={"A_DIRECT": 2, "B_INDIRECT": 1, "C_NEUTRAL": 2},
        status=status,
        error_message=None,
        started_at=datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC),
        completed_at=datetime(2026, 3, 15, 10, 0, 5, tzinfo=UTC),
        created_at=datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC),
    )


def _mock_thesis_score(
    issuer_id: uuid.UUID | None = None,
    plan2_run_id: uuid.UUID | None = None,
    eligible: bool = True,
    bucket: str = "A_DIRECT",
    thesis_rank_score: float = 78.5,
    thesis_rank: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        plan2_run_id=plan2_run_id or uuid.uuid4(),
        issuer_id=issuer_id or uuid.uuid4(),
        eligible=eligible,
        eligibility_json={"eligible_for_plan2": eligible, "failed_reasons": []},
        direct_commodity_exposure_score=90.0 if eligible else None,
        indirect_commodity_exposure_score=10.0 if eligible else None,
        export_fx_leverage_score=54.0 if eligible else None,
        final_commodity_affinity_score=52.0 if eligible else None,
        refinancing_stress_score=30.0 if eligible else None,
        usd_debt_exposure_score=30.0 if eligible else None,
        usd_import_dependence_score=20.0 if eligible else None,
        usd_revenue_offset_score=63.0 if eligible else None,
        final_dollar_fragility_score=32.4 if eligible else None,
        bucket=bucket if eligible else None,
        thesis_rank_score=thesis_rank_score if eligible else None,
        thesis_rank=thesis_rank if eligible else None,
        feature_input_json={
            "provenance": {
                "refinancing_stress": {
                    "source_type": "QUANTITATIVE",
                    "source_version": "quant-v1",
                    "assessed_at": "2026-03-15",
                    "assessed_by": None,
                    "confidence": "high",
                    "evidence_ref": None,
                },
                "direct_commodity_exposure": {
                    "source_type": "SECTOR_PROXY",
                    "source_version": "sector-proxy-v1",
                    "assessed_at": "2026-03-15",
                    "assessed_by": None,
                    "confidence": "low",
                    "evidence_ref": "sector=Extração Mineral",
                },
                "indirect_commodity_exposure": {
                    "source_type": "SECTOR_PROXY",
                    "source_version": "sector-proxy-v1",
                    "assessed_at": "2026-03-15",
                    "assessed_by": None,
                    "confidence": "low",
                    "evidence_ref": None,
                },
                "export_fx_leverage": {
                    "source_type": "DERIVED",
                    "source_version": "b2-assembly-v1",
                    "assessed_at": "2026-03-15",
                    "assessed_by": None,
                    "confidence": "low",
                    "evidence_ref": "derived: direct_commodity_exposure(90.0) * 0.6",
                },
                "usd_debt_exposure": {
                    "source_type": "DEFAULT",
                    "source_version": "b2-assembly-v1",
                    "assessed_at": "2026-03-15",
                    "assessed_by": None,
                    "confidence": "low",
                    "evidence_ref": None,
                },
                "usd_import_dependence": {
                    "source_type": "DEFAULT",
                    "source_version": "b2-assembly-v1",
                    "assessed_at": "2026-03-15",
                    "assessed_by": None,
                    "confidence": "low",
                    "evidence_ref": None,
                },
                "usd_revenue_offset": {
                    "source_type": "DERIVED",
                    "source_version": "b2-assembly-v1",
                    "assessed_at": "2026-03-15",
                    "assessed_by": None,
                    "confidence": "low",
                    "evidence_ref": "derived: direct_commodity_exposure(90.0) * 0.7",
                },
            },
        },
        explanation_json={
            "ticker": "VALE3",
            "bucket": "A_DIRECT",
            "thesis_rank_score": 78.5,
            "positives": ["Alta exposicao direta a commodities"],
            "negatives": [],
            "summary": "Empresa diretamente alavancada ao ciclo de commodities, com fragilidade controlada ao dolar.",
        },
    )


def _mock_issuer(
    issuer_id: uuid.UUID | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=issuer_id or uuid.uuid4(),
        cvm_code="4170",
        legal_name="Vale S.A.",
        trade_name="VALE3",
        sector="Extração Mineral",
        subsector=None,
    )


# =====================================================================
# Tests
# =====================================================================


class TestListRuns:
    def test_returns_list(self) -> None:
        run = _mock_plan2_run()
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = [run]

        client = _create_test_app(session)
        resp = client.get("/plan2/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["status"] == "completed"
        assert data[0]["total_eligible"] == 5

    def test_empty_list(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        client = _create_test_app(session)
        resp = client.get("/plan2/runs")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetRun:
    def test_returns_run(self) -> None:
        run = _mock_plan2_run()
        session = MagicMock()
        session.execute.return_value.scalar_one_or_none.return_value = run

        client = _create_test_app(session)
        resp = client.get(f"/plan2/runs/{run.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["thesis_config_version"] == "1.0.0"

    def test_not_found(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalar_one_or_none.return_value = None

        client = _create_test_app(session)
        resp = client.get(f"/plan2/runs/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestGetRanking:
    def _setup_ranking(self) -> tuple[TestClient, uuid.UUID]:
        run_id = uuid.uuid4()
        issuer_id = uuid.uuid4()
        run = _mock_plan2_run(run_id=run_id)
        score = _mock_thesis_score(issuer_id=issuer_id, plan2_run_id=run_id)
        issuer = _mock_issuer(issuer_id=issuer_id)

        session = MagicMock()
        # First call: get run, Second: get scores, Third: get issuers
        session.execute.return_value.scalar_one_or_none.return_value = run
        session.execute.return_value.scalars.return_value.all.side_effect = [
            [score],  # scores
            [issuer],  # issuers
        ]

        return _create_test_app(session), run_id

    def test_returns_ranking_with_coverage(self) -> None:
        client, run_id = self._setup_ranking()
        resp = client.get(f"/plan2/runs/{run_id}/ranking")
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_eligible"] == 5
        assert "evidence_distribution" in data
        assert "items" in data
        assert len(data["items"]) == 1

        item = data["items"][0]
        assert item["bucket"] == "A_DIRECT"
        assert item["eligible"] is True

        # Coverage must be present
        coverage = item["coverage"]
        assert coverage["total_dimensions"] == 7
        assert coverage["quantitative_count"] == 1
        assert coverage["sector_proxy_count"] == 2
        assert coverage["default_count"] == 2
        assert coverage["derived_count"] == 2
        assert coverage["evidence_quality"] == "MIXED_EVIDENCE"

    def test_evidence_distribution_present(self) -> None:
        client, run_id = self._setup_ranking()
        resp = client.get(f"/plan2/runs/{run_id}/ranking")
        data = resp.json()

        ev = data["evidence_distribution"]
        assert "high_evidence_count" in ev
        assert "mixed_evidence_count" in ev
        assert "low_evidence_count" in ev

    def test_not_found(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalar_one_or_none.return_value = None

        client = _create_test_app(session)
        resp = client.get(f"/plan2/runs/{uuid.uuid4()}/ranking")
        assert resp.status_code == 404


class TestGetIssuerDetail:
    def test_returns_detail_with_coverage(self) -> None:
        run_id = uuid.uuid4()
        issuer_id = uuid.uuid4()
        score = _mock_thesis_score(issuer_id=issuer_id, plan2_run_id=run_id)
        issuer = _mock_issuer(issuer_id=issuer_id)

        session = MagicMock()
        session.execute.return_value.scalar_one_or_none.side_effect = [score, issuer]

        client = _create_test_app(session)
        resp = client.get(f"/plan2/runs/{run_id}/issuer/{issuer_id}")
        assert resp.status_code == 200
        data = resp.json()

        assert data["eligible"] is True
        assert data["bucket"] == "A_DIRECT"
        assert "coverage" in data
        assert data["coverage"]["evidence_quality"] == "MIXED_EVIDENCE"
        assert "provenance" in data
        assert "feature_input_raw" in data

    def test_not_found(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalar_one_or_none.return_value = None

        client = _create_test_app(session)
        resp = client.get(f"/plan2/runs/{uuid.uuid4()}/issuer/{uuid.uuid4()}")
        assert resp.status_code == 404
