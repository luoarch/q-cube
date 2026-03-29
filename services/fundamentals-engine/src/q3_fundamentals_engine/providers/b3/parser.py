"""B3 COTAHIST fixed-width parser.

Parses daily trading data from B3's COTAHIST historical quotes files.
Format: fixed-width, Latin-1 encoding, ~245 chars per line.

Only mercado a vista (TPMERC=010) records are parsed.
Prices in centavos (N11V99) — divided by 100 for BRL.

Source: https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/mercado-a-vista/cotacoes-historicas/
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CotahistRecord:
    """One parsed COTAHIST trading record."""

    ticker: str
    date: date
    close: float      # PREULT in BRL (centavos / 100)
    open: float       # PREABE in BRL
    high: float       # PREMAX in BRL
    low: float        # PREMIN in BRL
    volume: float     # VOLTOT in BRL (centavos / 100)
    n_trades: int     # TOTNEG
    quantity: int     # QUATOT (shares traded)


# COTAHIST fixed-width field positions (0-indexed)
# Based on B3 layout specification
_TIPREG = slice(0, 2)
_DATA = slice(2, 10)
_CODBDI = slice(10, 12)
_CODNEG = slice(12, 24)
_TPMERC = slice(24, 27)
_PREABE = slice(56, 69)     # Open price (N11V99)
_PREMAX = slice(69, 82)     # High price
_PREMIN = slice(82, 95)     # Low price
_PREMED = slice(95, 108)    # Average price
_PREULT = slice(108, 121)   # Close price
_TOTNEG = slice(147, 152)   # Number of trades
_QUATOT = slice(152, 170)   # Quantity traded
_VOLTOT = slice(170, 188)   # Volume in BRL (N16V99)


def _parse_price(raw: str) -> float:
    """Parse B3 price field (N11V99) to float BRL. Centavos → reais."""
    return int(raw) / 100.0


def parse_cotahist_line(line: str) -> CotahistRecord | None:
    """Parse a single COTAHIST line. Returns None for header/trailer/non-vista."""
    if len(line) < 145:
        return None

    tipreg = line[_TIPREG]
    if tipreg != "01":
        return None  # Skip header (00) and trailer (99)

    tpmerc = line[_TPMERC]
    if tpmerc != "010":
        return None  # Only mercado a vista

    codbdi = line[_CODBDI]
    if codbdi != "02":
        return None  # Only lote padrao (02). Skip fracionario (96), exercicio (12), etc.

    try:
        ticker = line[_CODNEG].strip()
        dt = date(int(line[2:6]), int(line[6:8]), int(line[8:10]))
        close = _parse_price(line[_PREULT])
        open_ = _parse_price(line[_PREABE])
        high = _parse_price(line[_PREMAX])
        low = _parse_price(line[_PREMIN])
        volume = _parse_price(line[_VOLTOT]) if len(line) > 188 else 0.0
        n_trades = int(line[_TOTNEG]) if len(line) > 152 else 0
        quantity = int(line[_QUATOT]) if len(line) > 170 else 0
    except (ValueError, IndexError):
        return None

    if close <= 0:
        return None

    return CotahistRecord(
        ticker=ticker,
        date=dt,
        close=close,
        open=open_,
        high=high,
        low=low,
        volume=volume,
        n_trades=n_trades,
        quantity=quantity,
    )


def parse_cotahist(text: str) -> list[CotahistRecord]:
    """Parse full COTAHIST text content. Skips headers, trailers, non-vista."""
    records = []
    for line in text.split("\n"):
        line = line.rstrip("\r")
        if not line:
            continue
        rec = parse_cotahist_line(line)
        if rec is not None:
            records.append(rec)
    return records
