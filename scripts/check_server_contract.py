#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib import error, request

DEFAULT_BASE_URL = "http://127.0.0.1:8090"

REQUIRED_PATHS = [
    "/health",
    "/chat/messages",
    "/forest/projects/{project_name}/canopy/data",
]

REQUIRED_SYNC_GROUPS = [
    ["/forest/projects/{project_name}/status/sync"],
    ["/forest/projects/{project_name}/roadmap/sync"],
    ["/sync/handshake/init", "/sync/progress", "/sync/commit", "/sync/reconcile"],
    ["/api/sync/handshake/init", "/api/sync/progress", "/api/sync/commit", "/api/sync/reconcile"],
]


def _get_openapi(base_url: str, timeout: float = 5.0) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/openapi.json"
    req = request.Request(url, method="GET")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except error.URLError as exc:
        raise RuntimeError(f"openapi request failed: {exc}") from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("openapi response is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("openapi response is not an object")
    return parsed


def evaluate_contract(paths: set[str]) -> dict[str, Any]:
    missing_core = [path for path in REQUIRED_PATHS if path not in paths]
    sync_group_ok = any(all(path in paths for path in group) for group in REQUIRED_SYNC_GROUPS)
    detected_sync_prefix = ""
    if all(path in paths for path in REQUIRED_SYNC_GROUPS[0]):
        detected_sync_prefix = "forest/status-sync"
    elif all(path in paths for path in REQUIRED_SYNC_GROUPS[1]):
        detected_sync_prefix = "forest/roadmap-sync"
    elif all(path in paths for path in REQUIRED_SYNC_GROUPS[2]):
        detected_sync_prefix = "/sync"
    elif all(path in paths for path in REQUIRED_SYNC_GROUPS[3]):
        detected_sync_prefix = "/api/sync"

    missing_sync = []
    if not sync_group_ok:
        # expose the canonical sync route expectations when none of the accepted groups exist.
        missing_sync = REQUIRED_SYNC_GROUPS[2]

    ok = (not missing_core) and sync_group_ok
    return {
        "ok": ok,
        "missing_core": missing_core,
        "missing_sync": missing_sync,
        "sync_prefix": detected_sync_prefix or "unknown",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Sophia runtime server contract using OpenAPI.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()

    try:
        openapi = _get_openapi(str(args.base_url))
        raw_paths = openapi.get("paths", {})
        paths = set(raw_paths.keys()) if isinstance(raw_paths, dict) else set()
        result = evaluate_contract(paths)
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1

    payload = {
        "ok": bool(result["ok"]),
        "base_url": str(args.base_url),
        "path_count": len(paths),
        **result,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
