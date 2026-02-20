#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from api.config import settings
from core.forest.canopy import build_canopy_data, export_canopy_dashboard
from core.forest.layout import append_project_ledger_event, sanitize_project_name
from core.memory.schema import create_session_factory
from core.services.forest_status_service import sync_progress_snapshot


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Sophia Forest progress snapshot and roadmap.")
    parser.add_argument("--project", default="sophia", help="forest project name")
    parser.add_argument("--risk-threshold", type=float, default=0.8, help="risk threshold (0.0~1.0)")
    parser.add_argument(
        "--module-sort",
        choices=["importance", "progress", "risk"],
        default="importance",
        help="module sorting mode",
    )
    parser.add_argument(
        "--event-filter",
        choices=["all", "analysis", "work", "canopy", "question", "bitmap"],
        default="all",
        help="event filter used for snapshot source data",
    )
    parser.add_argument(
        "--export-canopy",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="also export canopy dashboard and snapshot",
    )
    return parser.parse_args()


def _sync_once(
    *,
    project_name: str,
    risk_threshold: float,
    module_sort: str,
    event_filter: str,
    export_canopy: bool,
) -> dict[str, Any]:
    session_factory = create_session_factory(settings.db_path)
    session = session_factory()
    try:
        canopy_data = build_canopy_data(
            project_name=project_name,
            session=session,
            risk_threshold=risk_threshold,
            module_sort=module_sort,
            event_filter=event_filter,
        )
        synced = sync_progress_snapshot(project_name=project_name, canopy_data=canopy_data)
        if isinstance(synced.get("snapshot"), dict):
            canopy_data["progress_sync"] = {"status": "synced", **dict(synced["snapshot"])}
        exported: dict[str, Any] = {}
        if export_canopy:
            exported = export_canopy_dashboard(project_name=project_name, data=canopy_data)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    status_summary = canopy_data.get("status_summary") if isinstance(canopy_data.get("status_summary"), dict) else {}
    append_project_ledger_event(
        project_name=project_name,
        event_type="STATUS_SYNCED",
        target=project_name,
        summary="project progress snapshot synced (script)",
        payload={
            "remaining_work": int(canopy_data.get("roadmap", {}).get("remaining_work", 0) or 0),
            "blocked": int(status_summary.get("BLOCKED", 0) or 0),
            "unverified": int(status_summary.get("UNVERIFIED", 0) or 0),
            "export_canopy": bool(export_canopy),
        },
    )

    return {
        "status": "ok",
        "project": project_name,
        "progress_snapshot_path": synced.get("snapshot_path", ""),
        "progress_roadmap_path": synced.get("roadmap_path", ""),
        "dashboard_path": str(exported.get("dashboard_path", "")),
        "canopy_snapshot_path": str(exported.get("snapshot_path", "")),
        "remaining_work": int(canopy_data.get("roadmap", {}).get("remaining_work", 0) or 0),
        "blocked": int(status_summary.get("BLOCKED", 0) or 0),
        "unverified": int(status_summary.get("UNVERIFIED", 0) or 0),
    }


def main() -> int:
    args = _parse_args()
    project_name = sanitize_project_name(args.project)
    payload = _sync_once(
        project_name=project_name,
        risk_threshold=float(args.risk_threshold),
        module_sort=str(args.module_sort),
        event_filter=str(args.event_filter),
        export_canopy=bool(args.export_canopy),
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
