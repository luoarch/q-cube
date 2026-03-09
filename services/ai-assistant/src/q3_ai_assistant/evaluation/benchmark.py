"""Benchmark fixtures for council agent quality evaluation.

Provides canonical asset archetypes (packets + expected behaviors) for
deterministic quality evaluation. Each fixture represents a well-understood
financial profile where the "correct" agent behavior is known.

Archetypes:
  - STRONG_COMPANY: clearly good — expect buy/watch consensus
  - VALUE_TRAP: high yield, deteriorating fundamentals — expect caution
  - BANK: financial classification — safety block skipped
  - INSUFFICIENT_DATA: minimal data — expect insufficient_data
  - ARTIFICIAL_DIVIDEND: payout > earnings — Barsi should flag
  - TURNAROUND: recent recovery from losses — mixed signals
  - UTILITY: regulated, stable margins — Barsi should like
  - CYCLICAL: volatile margins — expect lower confidence
  - DEEP_VALUE: cheap but ugly — Graham/Greenblatt should like
  - QUALITY_PREMIUM: expensive but high quality — Buffett should like
"""

from __future__ import annotations

from dataclasses import dataclass, field

from q3_ai_assistant.council.packet import AssetAnalysisPacket, DataCompleteness, PeriodValue
from q3_ai_assistant.council.types import AgentVerdict
from q3_ai_assistant.evaluation.quality import ConfidenceExpectation


def _pv(val: float | None, d: str = "2024-12-31") -> PeriodValue:
    return PeriodValue(reference_date=d, value=val)


def _make_packet(**overrides: object) -> AssetAnalysisPacket:
    defaults: dict[str, object] = dict(
        issuer_id="bench-id",
        ticker="BENCH3",
        sector="Bens Industriais",
        subsector="Maquinas e Equipamentos",
        classification="non_financial",
        fundamentals={},
        trends={},
        refiner_scores=None,
        flags=None,
        market_cap=None,
        avg_daily_volume=None,
        score_reliability="high",
    )
    defaults.update(overrides)
    return AssetAnalysisPacket(**defaults)  # type: ignore[arg-type]


@dataclass(frozen=True)
class BenchmarkCase:
    """A named benchmark scenario with packet + expected agent behaviors."""
    name: str
    description: str
    packet: AssetAnalysisPacket
    # Per-agent expected verdicts (None = any verdict acceptable)
    expected_verdicts: dict[str, list[AgentVerdict]] = field(default_factory=dict)
    # Per-agent expected confidence ranges
    expected_confidence: dict[str, ConfidenceExpectation] = field(default_factory=dict)
    # Hard rejects that should fire for each agent
    expected_hard_rejects: dict[str, list[str]] = field(default_factory=dict)
    # Hard rejects that should NOT fire
    expected_no_hard_rejects: dict[str, list[str]] = field(default_factory=dict)
    # Metrics that should appear in keyMetricsUsed
    expected_metrics_cited: dict[str, list[str]] = field(default_factory=dict)
    # Category for grouping
    category: str = "general"


# ---------------------------------------------------------------------------
# Archetype 1: Strong Company (easy consensus)
# ---------------------------------------------------------------------------

STRONG_COMPANY = BenchmarkCase(
    name="strong_company",
    description="Clearly good company — strong ROIC, margins, low debt, growing",
    category="consensus",
    packet=_make_packet(
        ticker="GOOD3",
        fundamentals={
            "earnings_yield": 0.10,
            "roic": 0.25,
            "roe": 0.22,
            "ebit": 500.0,
            "debt_to_ebitda": 1.0,
            "gross_margin": 0.45,
            "ebit_margin": 0.20,
            "net_margin": 0.15,
            "cash_conversion": 1.1,
            "equity": 2000.0,
        },
        trends={
            "roic": [_pv(0.22, "2022"), _pv(0.24, "2023"), _pv(0.25, "2024")],
            "roe": [_pv(0.20, "2022"), _pv(0.21, "2023"), _pv(0.22, "2024")],
            "gross_margin": [_pv(0.43, "2022"), _pv(0.44, "2023"), _pv(0.45, "2024")],
            "ebit_margin": [_pv(0.18, "2022"), _pv(0.19, "2023"), _pv(0.20, "2024")],
            "net_income": [_pv(350, "2022"), _pv(400, "2023"), _pv(450, "2024")],
            "cash_from_operations": [_pv(400, "2022"), _pv(450, "2023"), _pv(500, "2024")],
            "cash_from_investing": [_pv(-100, "2022"), _pv(-110, "2023"), _pv(-120, "2024")],
            "debt_to_ebitda": [_pv(1.2, "2022"), _pv(1.1, "2023"), _pv(1.0, "2024")],
        },
    ),
    expected_verdicts={
        "greenblatt": [AgentVerdict.buy, AgentVerdict.watch],
        "buffett": [AgentVerdict.buy, AgentVerdict.watch],
        "graham": [AgentVerdict.buy, AgentVerdict.watch],
        "barsi": [AgentVerdict.buy, AgentVerdict.watch],
    },
    expected_confidence={
        "greenblatt": ConfidenceExpectation(60, 95, "strong fundamentals"),
        "buffett": ConfidenceExpectation(60, 95, "strong fundamentals"),
    },
    expected_no_hard_rejects={
        "barsi": ["negative_fcf_3y", "negative_ni_recurring"],
        "graham": ["high_leverage_expensive", "negative_equity"],
        "greenblatt": ["negative_ebit", "roic_consistently_low"],
        "buffett": ["roe_consistently_low", "margin_collapse"],
    },
)

# ---------------------------------------------------------------------------
# Archetype 2: Value Trap
# ---------------------------------------------------------------------------

VALUE_TRAP = BenchmarkCase(
    name="value_trap",
    description="High yield but deteriorating margins + rising debt — looks cheap, is cheap for a reason",
    category="caution",
    packet=_make_packet(
        ticker="TRAP3",
        fundamentals={
            "earnings_yield": 0.15,
            "roic": 0.12,
            "roe": 0.10,
            "ebit": 200.0,
            "debt_to_ebitda": 4.5,
            "gross_margin": 0.18,
            "ebit_margin": 0.06,
            "net_margin": 0.03,
            "equity": 500.0,
        },
        trends={
            "gross_margin": [_pv(0.30, "2022"), _pv(0.24, "2023"), _pv(0.18, "2024")],
            "ebit_margin": [_pv(0.15, "2022"), _pv(0.10, "2023"), _pv(0.06, "2024")],
            "debt_to_ebitda": [_pv(2.0, "2022"), _pv(3.0, "2023"), _pv(4.5, "2024")],
            "net_income": [_pv(100, "2022"), _pv(80, "2023"), _pv(50, "2024")],
            "roic": [_pv(0.18, "2022"), _pv(0.15, "2023"), _pv(0.12, "2024")],
            "cash_from_operations": [_pv(120, "2022"), _pv(90, "2023"), _pv(60, "2024")],
            "cash_from_investing": [_pv(-80, "2022"), _pv(-90, "2023"), _pv(-100, "2024")],
        },
    ),
    expected_verdicts={
        "buffett": [AgentVerdict.avoid],  # margin_collapse triggers
        "greenblatt": [AgentVerdict.watch, AgentVerdict.avoid],  # declining ROIC
        "graham": [AgentVerdict.watch, AgentVerdict.avoid],  # rising debt
    },
    expected_hard_rejects={
        "buffett": ["margin_collapse"],  # 0.18 < 0.30 * 0.7 = 0.21
    },
    expected_confidence={
        "buffett": ConfidenceExpectation(60, 95, "hard reject fired"),
    },
)

# ---------------------------------------------------------------------------
# Archetype 3: Bank (classification-aware)
# ---------------------------------------------------------------------------

BANK = BenchmarkCase(
    name="bank",
    description="Financial institution — debt/EBITDA meaningless, safety rules skipped",
    category="classification",
    packet=_make_packet(
        ticker="BANK4",
        classification="bank",
        sector="Financeiro",
        subsector="Bancos",
        fundamentals={
            "roe": 0.18,
            "earnings_yield": 0.08,
            "net_margin": 0.25,
            "debt_to_ebitda": 15.0,  # meaningless for banks
            "equity": 50000.0,
        },
        trends={
            "roe": [_pv(0.16, "2022"), _pv(0.17, "2023"), _pv(0.18, "2024")],
            "net_income": [_pv(1000, "2022"), _pv(1100, "2023"), _pv(1200, "2024")],
        },
    ),
    expected_no_hard_rejects={
        "graham": ["high_leverage_expensive"],  # skips banks
    },
)

# ---------------------------------------------------------------------------
# Archetype 4: Insufficient Data
# ---------------------------------------------------------------------------

INSUFFICIENT_DATA = BenchmarkCase(
    name="insufficient_data",
    description="Minimal data — agents should acknowledge uncertainty",
    category="data_quality",
    packet=_make_packet(
        ticker="NODATA3",
        fundamentals={},
        trends={},
        score_reliability="unavailable",
        data_completeness=DataCompleteness(
            periods_available=0,
            metrics_available=0,
            metrics_expected=20,
            completeness_ratio=0.0,
            missing_critical=["revenue", "ebit", "net_income"],
        ),
    ),
    expected_verdicts={
        "greenblatt": [AgentVerdict.insufficient_data],
        "buffett": [AgentVerdict.insufficient_data],
        "graham": [AgentVerdict.insufficient_data],
        "barsi": [AgentVerdict.insufficient_data],
    },
    expected_confidence={
        "greenblatt": ConfidenceExpectation(0, 30, "no data at all"),
        "buffett": ConfidenceExpectation(0, 30, "no data at all"),
    },
)

# ---------------------------------------------------------------------------
# Archetype 5: Artificial Dividend
# ---------------------------------------------------------------------------

ARTIFICIAL_DIVIDEND = BenchmarkCase(
    name="artificial_dividend",
    description="Payout > 100% of earnings + rising debt = unsustainable dividends",
    category="caution",
    packet=_make_packet(
        ticker="FAKD3",
        fundamentals={
            "earnings_yield": 0.12,
            "roic": 0.08,
            "roe": 0.07,
            "ebit": 150.0,
            "debt_to_ebitda": 3.5,
            "gross_margin": 0.30,
            "net_margin": 0.05,
            "net_income": 80.0,
            "equity": 1000.0,
        },
        trends={
            "net_income": [_pv(120, "2022"), _pv(100, "2023"), _pv(80, "2024")],
            "cash_from_operations": [_pv(90, "2022"), _pv(70, "2023"), _pv(50, "2024")],
            "cash_from_investing": [_pv(-40, "2022"), _pv(-50, "2023"), _pv(-60, "2024")],
            "cash_from_financing": [_pv(-120, "2022"), _pv(-130, "2023"), _pv(-140, "2024")],
            "debt_to_ebitda": [_pv(2.0, "2022"), _pv(2.8, "2023"), _pv(3.5, "2024")],
            "roe": [_pv(0.10, "2022"), _pv(0.08, "2023"), _pv(0.07, "2024")],
        },
        qualitative_notes=[
            "Financing outflows exceed net income — dividends partly funded by debt",
        ],
    ),
    expected_verdicts={
        "barsi": [AgentVerdict.watch, AgentVerdict.avoid],  # unsustainable payout
        "buffett": [AgentVerdict.watch, AgentVerdict.avoid],  # declining ROE
    },
)

# ---------------------------------------------------------------------------
# Archetype 6: Turnaround
# ---------------------------------------------------------------------------

TURNAROUND = BenchmarkCase(
    name="turnaround",
    description="Was losing money, now recovering — recent positive EBIT, mixed signals",
    category="mixed",
    packet=_make_packet(
        ticker="TURN3",
        fundamentals={
            "earnings_yield": 0.06,
            "roic": 0.07,
            "roe": 0.05,
            "ebit": 80.0,
            "debt_to_ebitda": 3.0,
            "gross_margin": 0.28,
            "ebit_margin": 0.08,
            "net_margin": 0.02,
            "equity": 300.0,
        },
        trends={
            "ebit": [_pv(-50, "2022"), _pv(20, "2023"), _pv(80, "2024")],
            "net_income": [_pv(-80, "2022"), _pv(-10, "2023"), _pv(30, "2024")],
            "gross_margin": [_pv(0.22, "2022"), _pv(0.25, "2023"), _pv(0.28, "2024")],
            "roic": [_pv(-0.03, "2022"), _pv(0.02, "2023"), _pv(0.07, "2024")],
            "roe": [_pv(-0.08, "2022"), _pv(-0.01, "2023"), _pv(0.05, "2024")],
            "cash_from_operations": [_pv(-20, "2022"), _pv(30, "2023"), _pv(70, "2024")],
            "cash_from_investing": [_pv(-30, "2022"), _pv(-25, "2023"), _pv(-20, "2024")],
            "debt_to_ebitda": [_pv(8.0, "2022"), _pv(5.0, "2023"), _pv(3.0, "2024")],
        },
    ),
    expected_verdicts={
        "barsi": [AgentVerdict.avoid],  # negative NI recurring (2 of 3 years)
    },
    expected_hard_rejects={
        "barsi": ["negative_ni_recurring"],  # 2022 + 2023 are negative
    },
)

# ---------------------------------------------------------------------------
# Archetype 7: Utility (regulated)
# ---------------------------------------------------------------------------

UTILITY = BenchmarkCase(
    name="utility",
    description="Regulated utility — stable margins, predictable cash flows, Barsi archetype",
    category="classification",
    packet=_make_packet(
        ticker="UTIL11",
        classification="utility",
        sector="Utilidade Publica",
        subsector="Energia Eletrica",
        fundamentals={
            "earnings_yield": 0.09,
            "roic": 0.12,
            "roe": 0.15,
            "ebit": 600.0,
            "debt_to_ebitda": 2.5,
            "gross_margin": 0.35,
            "ebit_margin": 0.25,
            "net_margin": 0.12,
            "cash_conversion": 0.95,
            "equity": 3000.0,
        },
        trends={
            "roic": [_pv(0.11, "2022"), _pv(0.12, "2023"), _pv(0.12, "2024")],
            "roe": [_pv(0.14, "2022"), _pv(0.15, "2023"), _pv(0.15, "2024")],
            "gross_margin": [_pv(0.34, "2022"), _pv(0.35, "2023"), _pv(0.35, "2024")],
            "ebit_margin": [_pv(0.24, "2022"), _pv(0.25, "2023"), _pv(0.25, "2024")],
            "net_income": [_pv(250, "2022"), _pv(280, "2023"), _pv(300, "2024")],
            "cash_from_operations": [_pv(350, "2022"), _pv(370, "2023"), _pv(380, "2024")],
            "cash_from_investing": [_pv(-200, "2022"), _pv(-210, "2023"), _pv(-220, "2024")],
            "debt_to_ebitda": [_pv(2.8, "2022"), _pv(2.6, "2023"), _pv(2.5, "2024")],
        },
    ),
    expected_verdicts={
        "barsi": [AgentVerdict.buy, AgentVerdict.watch],  # Barsi loves utilities
        "greenblatt": [AgentVerdict.buy, AgentVerdict.watch],
    },
    expected_no_hard_rejects={
        "barsi": ["negative_fcf_3y", "negative_ni_recurring"],
        "buffett": ["roe_consistently_low", "margin_collapse"],
    },
)

# ---------------------------------------------------------------------------
# Archetype 8: Cyclical
# ---------------------------------------------------------------------------

CYCLICAL = BenchmarkCase(
    name="cyclical",
    description="Cyclical commodity company — volatile margins, agents should note uncertainty",
    category="mixed",
    packet=_make_packet(
        ticker="CYCL3",
        sector="Materiais Basicos",
        subsector="Mineracao",
        fundamentals={
            "earnings_yield": 0.18,
            "roic": 0.20,
            "roe": 0.18,
            "ebit": 800.0,
            "debt_to_ebitda": 1.5,
            "gross_margin": 0.40,
            "ebit_margin": 0.30,
            "net_margin": 0.20,
            "equity": 5000.0,
        },
        trends={
            "gross_margin": [_pv(0.50, "2022"), _pv(0.30, "2023"), _pv(0.40, "2024")],
            "ebit_margin": [_pv(0.40, "2022"), _pv(0.18, "2023"), _pv(0.30, "2024")],
            "roic": [_pv(0.30, "2022"), _pv(0.10, "2023"), _pv(0.20, "2024")],
            "net_income": [_pv(600, "2022"), _pv(200, "2023"), _pv(500, "2024")],
            "cash_from_operations": [_pv(700, "2022"), _pv(250, "2023"), _pv(550, "2024")],
            "cash_from_investing": [_pv(-200, "2022"), _pv(-150, "2023"), _pv(-180, "2024")],
        },
    ),
    expected_confidence={
        # Lower confidence expected due to volatility
        "buffett": ConfidenceExpectation(30, 75, "volatile cyclical"),
        "graham": ConfidenceExpectation(30, 75, "volatile cyclical"),
    },
)

# ---------------------------------------------------------------------------
# Archetype 9: Deep Value
# ---------------------------------------------------------------------------

DEEP_VALUE = BenchmarkCase(
    name="deep_value",
    description="Cheap on EY + ROIC, ugly low margins — Greenblatt/Graham should like it",
    category="value",
    packet=_make_packet(
        ticker="DEEP3",
        fundamentals={
            "earnings_yield": 0.20,
            "roic": 0.15,
            "roe": 0.12,
            "ebit": 300.0,
            "debt_to_ebitda": 2.0,
            "gross_margin": 0.22,
            "ebit_margin": 0.10,
            "net_margin": 0.06,
            "equity": 1500.0,
        },
        trends={
            "earnings_yield": [_pv(0.14, "2022"), _pv(0.17, "2023"), _pv(0.20, "2024")],
            "roic": [_pv(0.13, "2022"), _pv(0.14, "2023"), _pv(0.15, "2024")],
            "ebit": [_pv(250, "2022"), _pv(270, "2023"), _pv(300, "2024")],
            "gross_margin": [_pv(0.20, "2022"), _pv(0.21, "2023"), _pv(0.22, "2024")],
            "net_income": [_pv(100, "2022"), _pv(120, "2023"), _pv(150, "2024")],
            "cash_from_operations": [_pv(130, "2022"), _pv(150, "2023"), _pv(180, "2024")],
            "cash_from_investing": [_pv(-50, "2022"), _pv(-55, "2023"), _pv(-60, "2024")],
        },
    ),
    expected_verdicts={
        "greenblatt": [AgentVerdict.buy],  # High EY + ROIC
    },
    expected_confidence={
        "greenblatt": ConfidenceExpectation(65, 95, "strong EY + ROIC"),
    },
    expected_no_hard_rejects={
        "greenblatt": ["negative_ebit", "roic_consistently_low"],
    },
)

# ---------------------------------------------------------------------------
# Archetype 10: Quality Premium
# ---------------------------------------------------------------------------

QUALITY_PREMIUM = BenchmarkCase(
    name="quality_premium",
    description="Expensive on EY but exceptional quality — Buffett should favor, Greenblatt skeptical",
    category="divergence",
    packet=_make_packet(
        ticker="QUAL3",
        fundamentals={
            "earnings_yield": 0.04,  # expensive
            "roic": 0.30,
            "roe": 0.28,
            "ebit": 900.0,
            "debt_to_ebitda": 0.5,
            "gross_margin": 0.55,
            "ebit_margin": 0.30,
            "net_margin": 0.22,
            "cash_conversion": 1.2,
            "equity": 3000.0,
        },
        trends={
            "roic": [_pv(0.28, "2022"), _pv(0.29, "2023"), _pv(0.30, "2024")],
            "roe": [_pv(0.26, "2022"), _pv(0.27, "2023"), _pv(0.28, "2024")],
            "gross_margin": [_pv(0.53, "2022"), _pv(0.54, "2023"), _pv(0.55, "2024")],
            "ebit_margin": [_pv(0.28, "2022"), _pv(0.29, "2023"), _pv(0.30, "2024")],
            "net_income": [_pv(700, "2022"), _pv(800, "2023"), _pv(900, "2024")],
            "cash_from_operations": [_pv(800, "2022"), _pv(900, "2023"), _pv(1000, "2024")],
            "cash_from_investing": [_pv(-150, "2022"), _pv(-160, "2023"), _pv(-170, "2024")],
        },
    ),
    expected_verdicts={
        "buffett": [AgentVerdict.buy, AgentVerdict.watch],  # quality lover
        "greenblatt": [AgentVerdict.watch, AgentVerdict.avoid],  # EY too low for Magic Formula
        "graham": [AgentVerdict.watch, AgentVerdict.avoid],  # too expensive
    },
)


# ---------------------------------------------------------------------------
# All cases for parametrized testing
# ---------------------------------------------------------------------------

ALL_BENCHMARK_CASES: list[BenchmarkCase] = [
    STRONG_COMPANY,
    VALUE_TRAP,
    BANK,
    INSUFFICIENT_DATA,
    ARTIFICIAL_DIVIDEND,
    TURNAROUND,
    UTILITY,
    CYCLICAL,
    DEEP_VALUE,
    QUALITY_PREMIUM,
]

BENCHMARK_CASE_IDS = [c.name for c in ALL_BENCHMARK_CASES]


# ---------------------------------------------------------------------------
# Regression baseline
# ---------------------------------------------------------------------------

@dataclass
class BaselineEntry:
    """Stored baseline for regression detection."""
    case_name: str
    agent_id: str
    overall_score: float
    consistency: float
    groundedness: float
    framework_adherence: float


class RegressionBaseline:
    """Tracks quality score baselines and detects regressions.

    Usage:
        baseline = RegressionBaseline()
        baseline.record("strong_company", "greenblatt", score)
        drift = baseline.check_drift("strong_company", "greenblatt", new_score)
    """

    def __init__(self, threshold: float = 0.10) -> None:
        self.threshold = threshold
        self._entries: dict[str, BaselineEntry] = {}

    def _key(self, case_name: str, agent_id: str) -> str:
        return f"{case_name}:{agent_id}"

    def record(self, case_name: str, agent_id: str, score: object) -> None:
        self._entries[self._key(case_name, agent_id)] = BaselineEntry(
            case_name=case_name,
            agent_id=agent_id,
            overall_score=getattr(score, "overall", 0.0),
            consistency=getattr(score, "consistency", 0.0),
            groundedness=getattr(score, "groundedness", 0.0),
            framework_adherence=getattr(score, "framework_adherence", 0.0),
        )

    def check_drift(self, case_name: str, agent_id: str, current: object) -> dict:
        """Check if current score has regressed from baseline."""
        key = self._key(case_name, agent_id)
        entry = self._entries.get(key)
        if entry is None:
            return {"has_regression": False, "reason": "no baseline"}

        current_overall: float = getattr(current, "overall", 0.0)
        drift = entry.overall_score - current_overall
        is_regression = drift > self.threshold
        return {
            "has_regression": is_regression,
            "baseline": entry.overall_score,
            "current": current_overall,
            "drift": drift,
            "reason": f"Regressed by {drift:.2%}" if is_regression else "within threshold",
        }

    @property
    def entries(self) -> dict[str, BaselineEntry]:
        return dict(self._entries)
