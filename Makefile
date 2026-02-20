.PHONY: api api-local test-smoke forest-sync forest-loop forest-loop-auto check-server-contract

api:
	./scripts/run_api.sh

api-local:
	./scripts/run_api_local.sh

test-smoke:
	./scripts/test_smoke.sh

forest-sync:
	. .venv/bin/activate && ./scripts/sync_forest_status.py --project sophia --export-canopy

forest-loop:
	. .venv/bin/activate && ./scripts/sync_forest_loop.py --project sophia --intent "forest sync loop"

forest-loop-auto:
	. .venv/bin/activate && ./scripts/sync_forest_loop.py --project sophia --intent "forest sync loop" --from-git

check-server-contract:
	. .venv/bin/activate && ./scripts/check_server_contract.py --base-url http://127.0.0.1:8090
