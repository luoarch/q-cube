# ADR-007: Market Data Yahoo/yfinance Migration

## Status

Accepted

## Context

Q3's market data (prices, market_cap, volume) was sourced from BRAPI (brapi.dev). The free plan has limitations:

- 15K requests/month
- 3 months of history only
- Requires an API token
- Paid plans needed for deeper history (R$60/mo for 1yr)

These constraints limit backtest quality and add a paid dependency for what should be freely available market data.

## Decision

Migrate to **Yahoo Finance via yfinance** as the primary market data source for market snapshots. BRAPI is retained as a fallback provider.

Key design choices:

- **Provider protocol**: New `MarketSnapshotProvider` protocol separate from `FundamentalsProviderAdapter` (different interfaces)
- **Adapter pattern**: `YahooSnapshotAdapter` encapsulates all yfinance usage; the library is never imported outside the adapter
- **Ticker mapping**: `.SA` suffix applied inside adapter via `to_yahoo_ticker()` — Yahoo conventions never leak into domain
- **Factory**: `MarketSnapshotProviderFactory` resolves provider from `MARKET_SNAPSHOT_SOURCE` env var
- **Default source**: `MARKET_SNAPSHOT_SOURCE=yahoo` (free, no token needed)
- **Config flags**: `ENABLE_YAHOO=true` (default ON), alongside existing `ENABLE_BRAPI`

## Consequences

### Positive

- No API key required for market data
- Broader historical data available (yfinance supports multi-year history)
- Zero cost for the MVP
- Provider-agnostic pipeline — easy to add more sources later

### Negative

- yfinance is community-maintained (not an official Yahoo API)
- Yahoo may rate-limit or change their data format without notice
- No SLA or support contract

### Mitigations

- BRAPI retained as fallback (switch via env var)
- Adapter pattern isolates yfinance — replacing it only requires a new adapter class
- Seed scripts include rate limiting (0.5s between requests)

## References

- [yfinance on PyPI](https://pypi.org/project/yfinance/)
- BRAPI free plan docs: https://brapi.dev/docs
