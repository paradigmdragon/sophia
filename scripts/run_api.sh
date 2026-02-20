#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f ".venv/bin/activate" ]]; then
  echo "[run_api] .venv not found. Create it first: python3 -m venv .venv" >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

ASGI_APP="$(python scripts/find_asgi_app.py)"
echo "[run_api] ASGI app: ${ASGI_APP}"
echo "[run_api] Listening on 0.0.0.0:8090"

exec python -m uvicorn "$ASGI_APP" --host 0.0.0.0 --port 8090
