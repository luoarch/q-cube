import os


def ensure_psycopg_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("true", "1", "yes")


DATABASE_URL = ensure_psycopg_url(os.getenv("DATABASE_URL", "postgresql://127.0.0.1:5432/q3"))

# --- Feature flags (enable/disable data vendors via .env) ---
ENABLE_CVM = _flag("ENABLE_CVM", "true")             # CVM is the source of truth — on by default
ENABLE_BRAPI = _flag("ENABLE_BRAPI", "false")         # brapi.dev — off until token configured
ENABLE_DADOS_MERCADO = _flag("ENABLE_DADOS_MERCADO", "false")  # Dados de Mercado — off until token configured

# --- Dados de Mercado (primary for fundamentals) ---
# API docs: https://www.dadosdemercado.com.br/api/docs
# Issuer-centric: endpoints keyed by cvm_code
DADOS_MERCADO_BASE_URL = "https://api.dadosdemercado.com.br/v1"
DADOS_MERCADO_TOKEN = os.getenv("DADOS_MERCADO_TOKEN", "")

# --- brapi.dev (secondary for market data / enrichment) ---
# API docs: https://brapi.dev/docs
# Quote-centric: endpoints keyed by ticker
#
# Plan limits:
#   Gratuito: 15k req/month, 1 asset/req, 3mo history, NO fundamentals (BP/DRE/DFC)
#   Startup (R$24.99/mo): 150k req/month, 10 assets/req, 1yr history, annual fundamentals
#   Pro (R$49.99/mo): 500k req/month, 20 assets/req, 10yr+ history, full fundamentals
#
# On free plan, only quote/list and quote/{ticker} work (basic price/volume/marketCap).
# Modules (balanceSheetHistory, incomeStatementHistory, financialData, etc.) require Startup+.
BRAPI_BASE_URL = "https://brapi.dev/api"
BRAPI_TOKEN = os.getenv("BRAPI_TOKEN", "")

# --- CVM Portal Dados Abertos (source of truth / raw regulatory) ---
# Bulk download of ITR (quarterly) and DFP (annual) financial statements as CSVs.
# No authentication required. Updated weekly.
CVM_BASE_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC"

# CVM cadastro — company registration data (includes tickers via FCA)
CVM_CADASTRO_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"
