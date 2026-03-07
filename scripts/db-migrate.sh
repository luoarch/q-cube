#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -x "services/quant-engine/.venv/bin/python" ]]; then
  echo "[db-migrate] missing services/quant-engine/.venv/bin/python"
  echo "[db-migrate] run: pnpm bootstrap:local"
  exit 1
fi

DB_URL="${DATABASE_URL:-postgresql://127.0.0.1:5432/q3}"
DB_NAME="$(printf '%s' "$DB_URL" | sed -E 's#^postgresql(\+[^:]*)?://([^/]+/)?([^/?]+).*$#\3#')"

if [[ -n "$DB_NAME" ]]; then
  if ! psql "$DB_URL" -Atc "select 1" >/dev/null 2>&1; then
    echo "[db-migrate] database '$DB_NAME' not found or inaccessible, trying to create"
    createdb "$DB_NAME" || true
  fi
fi

echo "[db-migrate] applying alembic migrations"
(
  cd services/quant-engine
  DATABASE_URL="$DB_URL" .venv/bin/python -m q3_quant_engine.migrations
)

echo "[db-migrate] done"
