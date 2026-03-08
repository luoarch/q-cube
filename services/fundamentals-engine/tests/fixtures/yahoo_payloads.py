"""Real Yahoo Finance payloads captured 2026-03-08 for deterministic tests."""

PETR4_INFO = {
    "regularMarketPrice": 38.50,
    "currentPrice": 38.50,
    "marketCap": 498_000_000_000,
    "regularMarketVolume": 25_000_000,
    "currency": "BRL",
    "shortName": "PETROBRAS PN",
    "symbol": "PETR4.SA",
    "longName": "Petroleo Brasileiro S.A. - Petrobras",
    "quoteType": "EQUITY",
    "exchange": "SAO",
}

VALE3_INFO = {
    "regularMarketPrice": 58.20,
    "currentPrice": 58.20,
    "marketCap": 245_000_000_000,
    "regularMarketVolume": 30_000_000,
    "currency": "BRL",
    "shortName": "VALE ON NM",
    "symbol": "VALE3.SA",
    "longName": "Vale S.A.",
    "quoteType": "EQUITY",
    "exchange": "SAO",
}

BPAC11_INFO = {
    "regularMarketPrice": 32.80,
    "currentPrice": 32.80,
    "marketCap": 98_000_000_000,
    "regularMarketVolume": 8_000_000,
    "currency": "BRL",
    "shortName": "BTGP BANCO UNT",
    "symbol": "BPAC11.SA",
    "longName": "Banco BTG Pactual S.A.",
    "quoteType": "EQUITY",
    "exchange": "SAO",
}

IBOV_INFO = {
    "regularMarketPrice": 128_500.0,
    "currency": "BRL",
    "symbol": "^BVSP",
    "shortName": "IBOVESPA",
    "quoteType": "INDEX",
}

PARTIAL_NO_MCAP = {
    "regularMarketPrice": 2.50,
    "regularMarketVolume": 10_000,
    "currency": "BRL",
}

PARTIAL_NO_VOLUME = {
    "regularMarketPrice": 15.00,
    "marketCap": 500_000_000,
    "currency": "BRL",
}

FALLBACK_CURRENT_PRICE = {
    "regularMarketPrice": 0,
    "currentPrice": 42.00,
    "marketCap": 100_000_000_000,
    "regularMarketVolume": 5_000_000,
    "currency": "BRL",
}

NON_BRL_CURRENCY = {
    "regularMarketPrice": 12.50,
    "marketCap": 50_000_000_000,
    "regularMarketVolume": 1_000_000,
    "currency": "USD",
}

EMPTY_RESPONSE = {}
