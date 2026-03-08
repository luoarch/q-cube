import os


def ensure_psycopg_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("true", "1", "yes")


DATABASE_URL = ensure_psycopg_url(os.getenv("DATABASE_URL", "postgresql://127.0.0.1:5432/q3"))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# --- Feature flags ---
ENABLE_CVM = _flag("ENABLE_CVM", "true")
ENABLE_BRAPI = _flag("ENABLE_BRAPI", "false")
ENABLE_DADOS_MERCADO = _flag("ENABLE_DADOS_MERCADO", "false")
ENABLE_YAHOO = _flag("ENABLE_YAHOO", "true")

# --- Market snapshot source selection ---
MARKET_SNAPSHOT_SOURCE = os.getenv("MARKET_SNAPSHOT_SOURCE", "yahoo")
SNAPSHOT_STALENESS_DAYS = int(os.getenv("SNAPSHOT_STALENESS_DAYS", "7"))

# --- Canonical fundamentals migration flag ---
USE_CANONICAL_FUNDAMENTALS = _flag("USE_CANONICAL_FUNDAMENTALS", "false")

# --- Source selection policy ---
FUNDAMENTALS_SOURCE_ISSUER_MASTER = os.getenv("FUNDAMENTALS_SOURCE_ISSUER_MASTER", "cvm")
FUNDAMENTALS_SOURCE_STATEMENTS = os.getenv("FUNDAMENTALS_SOURCE_STATEMENTS", "cvm")
FUNDAMENTALS_SOURCE_MARKET_DATA = os.getenv("FUNDAMENTALS_SOURCE_MARKET_DATA", "cvm")
FUNDAMENTALS_SOURCE_INDICATORS = os.getenv("FUNDAMENTALS_SOURCE_INDICATORS", "internal")

# --- CVM URLs ---
CVM_BASE_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC"
CVM_CADASTRO_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"

# --- Dados de Mercado ---
DADOS_MERCADO_BASE_URL = "https://api.dadosdemercado.com.br/v1"
DADOS_MERCADO_TOKEN = os.getenv("DADOS_MERCADO_TOKEN", "")

# --- brapi.dev ---
BRAPI_BASE_URL = "https://brapi.dev/api"
BRAPI_TOKEN = os.getenv("BRAPI_TOKEN", "")
