#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

log() {
  printf '[bootstrap] %s\n' "$1"
}

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "comando obrigatório não encontrado: $1"
    exit 1
  fi
}

is_port_open() {
  local host="$1"
  local port="$2"
  (echo >"/dev/tcp/${host}/${port}") >/dev/null 2>&1
}

extract_host_port_from_url() {
  local url="$1"
  local default_host="$2"
  local default_port="$3"
  local host_port
  local host
  local port

  host_port="$(printf '%s' "$url" | sed -E 's#^[a-zA-Z0-9+.-]+://([^/@]+@)?([^/:?#]+)(:([0-9]+))?.*$#\2:\4#')"
  host="${host_port%%:*}"
  port="${host_port##*:}"

  if [[ -z "$host" || "$host" == "$host_port" ]]; then
    host="$default_host"
  fi

  if [[ -z "$port" || "$port" == "$host_port" ]]; then
    port="$default_port"
  fi

  printf '%s:%s\n' "$host" "$port"
}

ensure_python_service_env() {
  local service_dir="$1"
  local module_name="$2"
  local import_probe="$3"
  local service_abs="${ROOT_DIR}/${service_dir}"
  local venv_dir="${service_abs}/.venv"
  local venv_python="${venv_dir}/bin/python"

  if [[ ! -x "$venv_python" ]]; then
    log "criando virtualenv em ${venv_dir}"
    "$PYTHON_BIN" -m venv "$venv_dir"
  fi

  if ! "$venv_python" -c "$import_probe" >/dev/null 2>&1; then
    log "instalando dependências Python em ${service_dir}"
    "$venv_python" -m pip install --upgrade pip
    (
      cd "$service_abs"
      "$venv_python" -m pip install -e .[dev]
    )
  else
    log "dependências Python já instaladas em ${service_dir}"
  fi
}

# Tooling checks
need_cmd pnpm
need_cmd node

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  else
    log "comando obrigatório não encontrado: python ou python3"
    exit 1
  fi
fi

if [[ -f ".env" ]]; then
  log "carregando variáveis de ambiente de .env"
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
else
  log ".env não encontrado, seguindo com variáveis atuais do shell"
fi

# Service checks
PG_HOST="${PGHOST:-}"
PG_PORT="${PGPORT:-}"
REDIS_HOST="${REDIS_HOST:-}"
REDIS_PORT="${REDIS_PORT:-}"

if [[ -n "${DATABASE_URL:-}" ]]; then
  pg_host_port="$(extract_host_port_from_url "$DATABASE_URL" "127.0.0.1" "5432")"
  PG_HOST="${PG_HOST:-${pg_host_port%%:*}}"
  PG_PORT="${PG_PORT:-${pg_host_port##*:}}"
fi

if [[ -n "${REDIS_URL:-}" ]]; then
  redis_host_port="$(extract_host_port_from_url "$REDIS_URL" "127.0.0.1" "6379")"
  REDIS_HOST="${REDIS_HOST:-${redis_host_port%%:*}}"
  REDIS_PORT="${REDIS_PORT:-${redis_host_port##*:}}"
fi

PG_HOST="${PG_HOST:-127.0.0.1}"
PG_PORT="${PG_PORT:-5432}"
REDIS_HOST="${REDIS_HOST:-127.0.0.1}"
REDIS_PORT="${REDIS_PORT:-6379}"

log "validando PostgreSQL em ${PG_HOST}:${PG_PORT}"
if ! is_port_open "$PG_HOST" "$PG_PORT"; then
  log "PostgreSQL não acessível em ${PG_HOST}:${PG_PORT}"
  log "inicie seu PostgreSQL local e tente novamente"
  exit 1
fi

log "validando Redis em ${REDIS_HOST}:${REDIS_PORT}"
if ! is_port_open "$REDIS_HOST" "$REDIS_PORT"; then
  log "Redis não acessível em ${REDIS_HOST}:${REDIS_PORT}"
  log "inicie seu Redis local e tente novamente"
  exit 1
fi

if [[ ! -d node_modules ]]; then
  log "node_modules não encontrado, executando pnpm install"
  pnpm install
else
  log "dependências Node já instaladas"
fi

log "compilando pacotes compartilhados TypeScript"
pnpm --filter @q3/shared-contracts build
pnpm --filter @q3/api build

ensure_python_service_env \
  "services/quant-engine" \
  "q3_quant_engine" \
  "import uvicorn, sqlalchemy, alembic, q3_quant_engine"
ensure_python_service_env \
  "services/market-ingestion" \
  "q3_market_ingestion" \
  "import uvicorn, q3_market_ingestion"

if pnpm exec pm2 --version >/dev/null 2>&1; then
  PM2_CMD=(pnpm exec pm2)
else
  log "pm2 não encontrado nas dependências locais; verifique se o install concluiu com sucesso"
  exit 1
fi

log "subindo serviços via PM2"
"${PM2_CMD[@]}" start ecosystem.config.cjs

log "status dos processos"
"${PM2_CMD[@]}" status

log "bootstrap concluído"
