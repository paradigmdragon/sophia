#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _read_json(url: str, timeout: float = 5.0) -> dict[str, Any]:
    req = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        raise RuntimeError(f"http_error:{exc.code}:{url}") from exc
    except URLError as exc:
        raise RuntimeError(f"network_error:{url}:{exc}") from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"json_decode_error:{url}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"invalid_payload:{url}")
    return parsed


def _bool(value: Any) -> bool:
    return bool(value and str(value).strip())


def _check_files(project_root: Path) -> dict[str, bool]:
    status_dir = project_root / "status"
    dashboard_dir = project_root / "dashboard"
    return {
        "status_dir_exists": status_dir.exists(),
        "roadmap_journal_exists": (status_dir / "roadmap_journal.jsonl").exists(),
        "progress_snapshot_exists": (status_dir / "progress_snapshot.json").exists(),
        "dashboard_index_exists": (dashboard_dir / "index.html").exists(),
    }


def run(base_url: str, project: str, workspace: Path) -> dict[str, Any]:
    safe_base = base_url.rstrip("/")
    canopy = _read_json(f"{safe_base}/forest/projects/{project}/canopy/data")
    rv = canopy.get("roadmap_journal") if isinstance(canopy.get("roadmap_journal"), dict) else {}
    hv = canopy.get("human_view") if isinstance(canopy.get("human_view"), dict) else {}
    focus = canopy.get("focus") if isinstance(canopy.get("focus"), dict) else {}

    entries = rv.get("entries") if isinstance(rv.get("entries"), list) else []
    latest = entries[0] if entries else {}
    roadmap_now = hv.get("roadmap_now") if isinstance(hv.get("roadmap_now"), dict) else {}
    phase_counts = rv.get("phase_counts") if isinstance(rv.get("phase_counts"), dict) else {}

    checks = {
        "canopy_data_ok": isinstance(canopy, dict),
        "focus_mode_present": isinstance(focus.get("focus_mode"), bool),
        "roadmap_entries_present": len(entries) > 0,
        "latest_entry_has_recorded_at": _bool(latest.get("recorded_at")) or _bool(latest.get("timestamp")),
        "latest_entry_has_phase": _bool(latest.get("phase")),
        "latest_entry_has_phase_step": _bool(latest.get("phase_step")),
        "current_phase_present": _bool(rv.get("current_phase")),
        "current_phase_step_present": _bool(rv.get("current_phase_step")),
        "roadmap_now_next_action_present": _bool(roadmap_now.get("next_action")),
        "roadmap_now_mission_present": _bool(roadmap_now.get("current_mission_id")),
        "phase_counts_present": len(phase_counts) > 0,
    }

    project_root = workspace / "forest" / "project" / project
    file_checks = _check_files(project_root)
    checks.update(file_checks)

    failed = [key for key, ok in checks.items() if not ok]
    return {
        "status": "ok" if not failed else "warning",
        "project": project,
        "base_url": safe_base,
        "failed_checks": failed,
        "check_count": len(checks),
        "checks": checks,
        "snapshot": {
            "current_phase": rv.get("current_phase", ""),
            "current_phase_step": rv.get("current_phase_step", ""),
            "roadmap_entries": len(entries),
            "last_recorded_at": rv.get("last_recorded_at", ""),
            "current_mission_id": roadmap_now.get("current_mission_id"),
            "next_action": roadmap_now.get("next_action", ""),
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Sophia Forest handoff readiness")
    parser.add_argument("--base-url", default="http://127.0.0.1:8090")
    parser.add_argument("--project", default="sophia")
    parser.add_argument("--workspace", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--json", action="store_true", help="print json payload")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        result = run(
            base_url=str(args.base_url),
            project=str(args.project),
            workspace=Path(str(args.workspace)).resolve(),
        )
    except Exception as exc:  # pragma: no cover - runtime reporting path
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
