# Month 2 — LOW_CONFIDENCE Removals Audit

## Finding: 7/7 removed names would be APPROVED if confidence = MEDIUM

### The 7 names blocked by LOW_CONFIDENCE from Ranking Top-20

| Ticker | Quality | Yield | Conf | Risks | Would approve? |
|--------|:-------:|------:|:----:|:-----:|:--------------:|
| MYPK3 | **0.76** | 26.7% | 0.32 | 1 | YES |
| MMAQ3 | **0.75** | 108.1% | 0.32 | 0 | YES |
| GOAU3 | **0.71** | 65.2% | 0.30 | 0 | YES |
| POSI3 | 0.62 | 33.6% | 0.32 | 1 | YES |
| tgma3 | 0.60 | 21.0% | 0.30 | 0 | YES |
| KEPL3 | 0.57 | 35.9% | 0.32 | 0 | YES |
| NUTR3 | 0.55 | 45.1% | 0.30 | 1 | YES |

### Root cause

All 7 share the same pattern:
- `sector_fallback` penalty (-0.10) is universal (100% of tickers)
- Thesis missing for all → evidence_quality defaults to LOW/UNKNOWN
- This caps confidence at ~0.30-0.32, below MEDIUM threshold (0.40)

### Is this over-pruning?

| Cohort | Avg Quality |
|--------|:----------:|
| APPROVED (33) | 0.661 |
| LOW_CONF removed (7) | **0.650** |

Quality is nearly identical. These names are **fundamentally comparable** to the APPROVED cohort. The sole differentiator is confidence score — which is penalized by structural factors (sector size, thesis coverage), not by data quality.

### Interpretation

This is **systematic false-negative from confidence calibration**, not from bad data or weak fundamentals. The confidence system is correctly identifying incomplete evidence, but the penalty structure makes it impossible for these names to reach MEDIUM — even with perfect refiner data.

### Implication (post-pilot)

After the pilot (frozen rules), confidence recalibration should consider:
- Reducing sector_fallback penalty (from -0.10 to -0.05), OR
- Raising the minimum sector size threshold (from 5 to 3), OR
- Separating "data incomplete" from "evidence weak" in confidence scoring

### During pilot

**No changes.** This is documented as a known systematic bias. The pilot measures whether APPROVED (without these 7) generates signal — if it does, adding them later only improves coverage.
