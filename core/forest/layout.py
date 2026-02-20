from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[2]
FOREST_ROOT = BASE_DIR / "forest" / "project"
DEFAULT_PROJECT = "sophia"


REQUIRED_SUBDIRS = [
    "docs",
    "analysis",
    "ledger",
    "backlog",
    "questions",
    "status",
    "work",
    "dashboard",
]


def sanitize_project_name(project_name: str) -> str:
    raw = (project_name or "").strip().lower()
    if not raw:
        return DEFAULT_PROJECT
    safe = re.sub(r"[^a-z0-9._-]+", "-", raw).strip("-")
    return safe or DEFAULT_PROJECT


def get_project_root(project_name: str = DEFAULT_PROJECT) -> Path:
    safe = sanitize_project_name(project_name)
    return FOREST_ROOT / safe


def list_project_names() -> list[str]:
    FOREST_ROOT.mkdir(parents=True, exist_ok=True)
    names = sorted(
        [
            sanitize_project_name(path.name)
            for path in FOREST_ROOT.iterdir()
            if path.is_dir() and sanitize_project_name(path.name)
        ]
    )
    if DEFAULT_PROJECT not in names:
        names.insert(0, DEFAULT_PROJECT)
    return names


def ensure_project_layout(project_name: str = DEFAULT_PROJECT) -> dict[str, str]:
    root = get_project_root(project_name)
    root.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {"project_root": str(root)}
    for subdir in REQUIRED_SUBDIRS:
        p = root / subdir
        p.mkdir(parents=True, exist_ok=True)
        paths[subdir] = str(p)
    return paths


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        f.flush()


def append_project_ledger_event(
    *,
    project_name: str,
    event_type: str,
    target: str,
    summary: str,
    payload: dict[str, Any] | None = None,
) -> Path:
    ensure_project_layout(project_name)
    ledger_path = get_project_root(project_name) / "ledger" / "ledger.jsonl"
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    row = {
        "timestamp": now,
        "event_type": event_type,
        "target": target,
        "summary": summary,
    }
    if payload:
        row["payload"] = payload
    append_jsonl(ledger_path, row)
    return ledger_path
