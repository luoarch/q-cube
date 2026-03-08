"""AssetAnalysisPacket — SSOT input for all council agents.

Built from existing data sources: computed_metrics, statement_lines,
refinement_results, market_snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PeriodValue:
    reference_date: str
    value: float | None


@dataclass
class DataCompleteness:
    periods_available: int
    metrics_available: int
    metrics_expected: int
    completeness_ratio: float
    missing_critical: list[str] = field(default_factory=list)
    proxy_used: list[str] = field(default_factory=list)


@dataclass
class AssetAnalysisPacket:
    """SSOT data packet fed to every council agent.

    All factual claims must be sourced from this packet.
    Agents must not infer or fabricate financial facts outside it.
    """
    issuer_id: str
    ticker: str
    sector: str
    subsector: str
    classification: str  # non_financial / bank / insurer / utility / holding

    # From computed_metrics (latest + 3-period)
    fundamentals: dict[str, float | None]  # current values
    trends: dict[str, list[PeriodValue]]  # 3-period series

    # From refinement_results (if available)
    refiner_scores: dict[str, float] | None
    flags: dict[str, list[str]] | None

    # From market_snapshots
    market_cap: float | None
    avg_daily_volume: float | None

    # Qualitative
    qualitative_notes: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)

    # Data quality
    data_completeness: DataCompleteness | None = None
    score_reliability: str = "unavailable"

    # Metadata
    as_of_date: str = ""
    source_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize for prompt injection."""
        return {
            "ticker": self.ticker,
            "sector": self.sector,
            "subsector": self.subsector,
            "classification": self.classification,
            "fundamentals": self.fundamentals,
            "trends": {
                k: [{"date": pv.reference_date, "value": pv.value} for pv in v]
                for k, v in self.trends.items()
            },
            "refinerScores": self.refiner_scores,
            "flags": self.flags,
            "marketCap": self.market_cap,
            "avgDailyVolume": self.avg_daily_volume,
            "qualitativeNotes": self.qualitative_notes,
            "riskFlags": self.risk_flags,
            "scoreReliability": self.score_reliability,
            "asOfDate": self.as_of_date,
        }
