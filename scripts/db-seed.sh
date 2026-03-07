#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -x "services/quant-engine/.venv/bin/python" ]]; then
  echo "[db-seed] missing services/quant-engine/.venv/bin/python"
  echo "[db-seed] run: pnpm bootstrap:local"
  exit 1
fi

echo "[db-seed] seeding demo data"
(
  cd services/quant-engine
  DATABASE_URL="${DATABASE_URL:-postgresql://127.0.0.1:5432/q3}" .venv/bin/python -m q3_quant_engine.seeds
)

echo "[db-seed] done"
