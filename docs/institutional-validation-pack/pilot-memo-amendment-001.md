# Pilot Memo — Amendment 001

## Date: 2026-03-23 (Month 1 deep analysis)

## Formal methodological note

> Current confidence gate appears over-conservative under current sector/thesis coverage regime and may generate prudent but systematic false negatives. The sector_fallback penalty (-0.10) applies universally (100% of tickers due to small CVM sector sizes), and thesis coverage at 11% means evidence_quality defaults to LOW for most issuers. Combined, these structural factors cap confidence at 0.30-0.32 for the majority of the universe, below the MEDIUM threshold (0.40) required for APPROVED status.

## Evidence

- 7/7 names removed from Ranking Top-20 by LOW_CONFIDENCE would be APPROVED if confidence reached MEDIUM
- Avg quality of removed names (0.650) ≈ avg quality of APPROVED cohort (0.661)
- Sole differentiator is confidence score, driven by calibration, not data quality
- Zero HIGH confidence across entire 192-ticker universe

## Impact on pilot interpretation

- BLOCKED counts are inflated by confidence-structural false negatives
- BLOCKED should be read as two distinct sub-populations:
  - **BLOCKED_CONFIDENCE_STRUCTURAL**: blocked solely by confidence calibration (likely false negatives)
  - **BLOCKED_OTHER**: blocked by LOW_YIELD, MARGINAL, or DATA_MISSING (legitimate blocks)
- Forward return analysis should track the confidence-removed cohort separately

## Status

- No rule changes authorized during pilot
- Confidence recalibration is a mandatory post-pilot follow-up
- This amendment is append-only to the pilot record

## Approved by

Tech Lead review, 2026-03-23.
