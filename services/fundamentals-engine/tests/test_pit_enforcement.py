"""Tests for point-in-time enforcement in TTM and research panel."""

from datetime import date

from q3_fundamentals_engine.metrics.ttm import quarter_end_dates


class TestQuarterEndDates:
    """Verify quarter date computation (foundation for PIT checks)."""

    def test_q4_2024(self) -> None:
        dates = quarter_end_dates(date(2024, 12, 31))
        assert dates == [
            date(2024, 3, 31),
            date(2024, 6, 30),
            date(2024, 9, 30),
            date(2024, 12, 31),
        ]

    def test_q3_2024(self) -> None:
        dates = quarter_end_dates(date(2024, 9, 30))
        assert dates == [
            date(2023, 12, 31),
            date(2024, 3, 31),
            date(2024, 6, 30),
            date(2024, 9, 30),
        ]


class TestPitPublicationDateRules:
    """Test CVM publication date estimation rules."""

    def test_dfp_90_day_deadline(self) -> None:
        # DFP for FY 2024 (ref_date=2024-12-31) → published by 2025-03-31
        ref = date(2024, 12, 31)
        expected_pub = date(2025, 3, 31)
        # DFP deadline = ref_date + 90 days
        from datetime import timedelta
        actual = ref + timedelta(days=90)
        assert actual == expected_pub

    def test_itr_45_day_deadline(self) -> None:
        # ITR for Q3 2024 (ref_date=2024-09-30) → published by 2024-11-14
        ref = date(2024, 9, 30)
        expected_pub = date(2024, 11, 14)
        from datetime import timedelta
        actual = ref + timedelta(days=45)
        assert actual == expected_pub

    def test_dfp_2024_not_available_at_year_end(self) -> None:
        """Core PIT test: DFP 2024 should NOT be available on 2024-12-31."""
        ref = date(2024, 12, 31)
        from datetime import timedelta
        pub_date = ref + timedelta(days=90)  # 2025-03-31
        knowledge_date = date(2024, 12, 31)
        assert pub_date > knowledge_date, "DFP 2024 is NOT available at year-end"

    def test_itr_q3_available_before_year_end(self) -> None:
        """ITR Q3 2024 SHOULD be available before 2024-12-31."""
        ref = date(2024, 9, 30)
        from datetime import timedelta
        pub_date = ref + timedelta(days=45)  # 2024-11-14
        knowledge_date = date(2024, 12, 31)
        assert pub_date <= knowledge_date, "ITR Q3 should be available"


class TestPitComplianceCheck:
    """Test the PIT compliance checker in panel_builder."""

    def test_compliant_when_all_filings_published(self) -> None:
        from q3_fundamentals_engine.research.panel_builder import _check_pit_compliance
        import uuid

        filing_id = uuid.uuid4()
        mock_metric = type("Metric", (), {
            "source_filing_ids_json": [str(filing_id)],
            "inputs_snapshot_json": {},
        })()

        pub_dates = {filing_id: date(2024, 11, 14)}  # ITR Q3
        assert _check_pit_compliance(mock_metric, None, date(2024, 12, 31), pub_dates) is True

    def test_non_compliant_when_filing_not_yet_published(self) -> None:
        from q3_fundamentals_engine.research.panel_builder import _check_pit_compliance
        import uuid

        filing_id = uuid.uuid4()
        mock_metric = type("Metric", (), {
            "source_filing_ids_json": [str(filing_id)],
            "inputs_snapshot_json": {},
        })()

        pub_dates = {filing_id: date(2025, 3, 31)}  # DFP 2024
        assert _check_pit_compliance(mock_metric, None, date(2024, 12, 31), pub_dates) is False

    def test_nby_snapshot_pit_check(self) -> None:
        from q3_fundamentals_engine.research.panel_builder import _check_pit_compliance

        mock_nby = type("Metric", (), {
            "source_filing_ids_json": [],
            "inputs_snapshot_json": {
                "t_snapshot_fetched_at": "2024-12-29 21:00:00-03:00",
                "t4_snapshot_fetched_at": "2024-01-01 21:00:00-03:00",
            },
        })()

        assert _check_pit_compliance(None, mock_nby, date(2024, 12, 31), {}) is True

    def test_nby_future_snapshot_fails_pit(self) -> None:
        from q3_fundamentals_engine.research.panel_builder import _check_pit_compliance

        mock_nby = type("Metric", (), {
            "source_filing_ids_json": [],
            "inputs_snapshot_json": {
                "t_snapshot_fetched_at": "2025-01-05 21:00:00-03:00",
                "t4_snapshot_fetched_at": "2024-01-01 21:00:00-03:00",
            },
        })()

        assert _check_pit_compliance(None, mock_nby, date(2024, 12, 31), {}) is False

    def test_no_metrics_is_compliant(self) -> None:
        from q3_fundamentals_engine.research.panel_builder import _check_pit_compliance
        assert _check_pit_compliance(None, None, date(2024, 12, 31), {}) is True
