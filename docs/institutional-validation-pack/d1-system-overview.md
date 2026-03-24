# Q3 — Decision-Support Research System for B3 Equity Selection

## What Q3 Is

A deterministic, auditable equity screening and decision system for the Brazilian market (B3). It ranks, evaluates, and classifies assets using CVM filings and public market data — producing per-ticker research classifications (APPROVED / BLOCKED / REJECTED) with full provenance.

## Architecture

```
CVM Filings (DFP/ITR) ──→ Fundamentals Pipeline ──→ Computed Metrics (15)
Yahoo Market Data ─────→ Market Snapshots ─────→ Compat View (26 cols)
                                                        │
                                              ┌─────────▼──────────┐
                                              │   Ranking Engine    │
                                              │  (EY + ROC, 3 var) │
                                              └─────────┬──────────┘
                                                        │
                                              ┌─────────▼──────────┐
                                              │     Refiner        │
                                              │ (4 quality blocks) │
                                              └─────────┬──────────┘
                                                        │
                                              ┌─────────▼──────────┐
                                              │  Decision Engine   │
                                              │ Quality+Val+Yield  │
                                              │ Drivers+Risks+Call │
                                              └─────────┬──────────┘
                                                        │
                                              ┌─────────▼──────────┐
                                              │    Governance      │
                                              │ Registry+Guardrails│
                                              └────────────────────┘
```

## Data Sources

| Source | Type | Cost |
|--------|------|:----:|
| CVM DFP/ITR (2020-2024) | Financial statements | Free |
| CVM Composição do Capital | Share counts | Free |
| CVM Cadastro/FCA | Issuer metadata | Free |
| Yahoo Finance | Market prices, volume | Free |

No paid vendors. No proprietary data. Fully reproducible.

## Coverage

| Layer | Current | Data-eligible max |
|-------|--------:|:--------:|
| Universe (CORE_ELIGIBLE) | 242 issuers | — |
| With earnings yield | 196 (81%) | — |
| With market data | 194 (80%) | — |
| With thesis scoring | 120 (50%) | 242 |
| With refiner quality | **38 (16%)** | **196** |
| Full decision pipeline | **38** | **196** |

## Refusal Rate

- **57% BLOCKED** in top-50 sample (17/30 in top-30)
- **67% valuation proxy suppressed** (sanity guard: upside > 300%)
- **82% of BLOCKEDs are contingent** on refiner coverage, not structural inability

The system refuses to opine when evidence is insufficient. This is by design.

## What Q3 Is NOT

- **Not** an investment recommender — outputs are research classifications
- **Not** a DCF valuation engine — uses EY normalization proxy
- **Not** a production allocator — no position sizing, no execution
- **Not** forward-looking — implied yield is static (no growth assumptions)
- **Not** a replacement for human judgment — augments, does not replace

## Current Limits

1. Refiner covers 16% of eligible universe (operational gap, not architectural)
2. Proxy valuation suppressed in 67% of cheap names (EV distortion)
3. No forward return validation of APPROVED vs BLOCKED classification yet
4. Strategy (hybrid_20q) not promoted — blocked by OOS dispersion
5. Benchmark is price-only Ibovespa (no dividend reinvestment)
6. Output is research classification, not executable recommendation
