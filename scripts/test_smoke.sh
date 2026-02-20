#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f ".venv/bin/activate" ]]; then
  echo "[test-smoke] .venv not found. Create it first: python3 -m venv .venv" >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

ASGI_APP="$(python scripts/find_asgi_app.py)"
LOG_FILE="$(mktemp -t sophia_api_smoke)"
SERVER_PID=""
STARTED_LOCAL_SERVER="false"

if lsof -nP -iTCP:8090 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "[test-smoke] Existing server detected on 8090. Reusing running server."
  if ! curl -sS -o /tmp/sophia_health_smoke.json -w '%{http_code}' http://127.0.0.1:8090/health | grep -q '^200$'; then
    echo "[test-smoke] Existing 8090 listener is not healthy(/health != 200)." >&2
    lsof -nP -iTCP:8090 -sTCP:LISTEN || true
    exit 1
  fi
else
  python -m uvicorn "$ASGI_APP" --host 0.0.0.0 --port 8090 >"$LOG_FILE" 2>&1 &
  SERVER_PID=$!
  STARTED_LOCAL_SERVER="true"
fi

cleanup() {
  if [[ "$STARTED_LOCAL_SERVER" == "true" ]] && [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" >/dev/null 2>&1; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
    wait "$SERVER_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

for _ in $(seq 1 50); do
  if lsof -nP -iTCP:8090 -sTCP:LISTEN >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

LISTEN_INFO="$(lsof -nP -iTCP:8090 -sTCP:LISTEN | tail -n +2 || true)"
if [[ -z "$LISTEN_INFO" ]]; then
  echo "[test-smoke] Server did not start on 8090" >&2
  if [[ -f "$LOG_FILE" ]]; then
    tail -n 80 "$LOG_FILE" >&2 || true
  fi
  exit 1
fi

if [[ "$STARTED_LOCAL_SERVER" == "true" ]]; then
  if ! echo "$LISTEN_INFO" | grep -Eq 'TCP (\*|0\.0\.0\.0):8090 \(LISTEN\)'; then
    echo "[test-smoke] 8090 is not listening on 0.0.0.0/*" >&2
    echo "$LISTEN_INFO" >&2
    exit 1
  fi
  echo "[test-smoke] LISTEN check OK (0.0.0.0)"
else
  if echo "$LISTEN_INFO" | grep -Eq 'TCP (\*|0\.0\.0\.0):8090 \(LISTEN\)'; then
    echo "[test-smoke] LISTEN check OK (existing server, 0.0.0.0)"
  else
    echo "[test-smoke] LISTEN check WARN (existing server is local-only):"
    echo "$LISTEN_INFO"
  fi
fi

CHAT_STATUS="$(curl -sS -o /tmp/sophia_chat_smoke.json -w '%{http_code}' -X POST http://127.0.0.1:8090/chat/messages -H 'Content-Type: application/json' -d '{"message":"smoke test","mode":"chat"}')"
if [[ "$CHAT_STATUS" != "200" ]]; then
  echo "[test-smoke] /chat/messages failed: HTTP $CHAT_STATUS" >&2
  cat /tmp/sophia_chat_smoke.json >&2 || true
  exit 1
fi

echo "[test-smoke] /chat/messages OK (200)"

DOCS_STATUS="$(curl -sS -o /tmp/sophia_docs_smoke.html -w '%{http_code}' http://127.0.0.1:8090/docs)"
if [[ "$DOCS_STATUS" != "200" && "$DOCS_STATUS" != "302" ]]; then
  echo "[test-smoke] /docs failed: HTTP $DOCS_STATUS" >&2
  exit 1
fi

echo "[test-smoke] /docs OK ($DOCS_STATUS)"

OPENAPI_STATUS="$(curl -sS -o /tmp/sophia_openapi_smoke.json -w '%{http_code}' http://127.0.0.1:8090/openapi.json)"
if [[ "$OPENAPI_STATUS" != "200" ]]; then
  echo "[test-smoke] /openapi.json failed: HTTP $OPENAPI_STATUS" >&2
  exit 1
fi

echo "[test-smoke] /openapi.json OK (200)"

python ./scripts/check_server_contract.py --base-url http://127.0.0.1:8090 >/tmp/sophia_contract_smoke.json
CONTRACT_EXIT=$?
if [[ "$CONTRACT_EXIT" -ne 0 ]]; then
  echo "[test-smoke] server contract check failed" >&2
  cat /tmp/sophia_contract_smoke.json >&2 || true
  exit 1
fi

echo "[test-smoke] server contract OK"

echo "[test-smoke] PASS"
