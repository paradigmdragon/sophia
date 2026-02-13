from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path


MEMORY_ROOT = Path("/Users/dragonpd/Sophia/sophia_workspace/memory")
_NAMESPACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sanitize_namespace(namespace: str) -> str:
    if not isinstance(namespace, str) or not namespace.strip():
        raise ValueError("inputs.namespace must be a non-empty string")

    value = namespace.strip()
    if "/" in value or "\\" in value or value in {".", ".."}:
        raise ValueError("inputs.namespace contains invalid path characters")
    if not _NAMESPACE_RE.match(value):
        raise ValueError("inputs.namespace contains unsupported characters")
    return value


def run(inputs: dict) -> dict:
    namespace_raw = inputs.get("namespace")
    data = inputs.get("data")

    if not isinstance(data, dict):
        raise ValueError("inputs.data must be a dict")

    namespace = _sanitize_namespace(namespace_raw)

    root = MEMORY_ROOT.resolve()
    root.mkdir(parents=True, exist_ok=True)

    target = (root / f"{namespace}.jsonl").resolve()
    if target.parent != root:
        raise PermissionError("namespace path is outside memory root")

    record = {"ts": _utc_now(), "data": data}
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())

    return {"namespace": namespace, "records_appended": 1}
