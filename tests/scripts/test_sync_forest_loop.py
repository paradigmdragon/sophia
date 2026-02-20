from __future__ import annotations

import json
from pathlib import Path

from scripts.sync_forest_loop import (
    SyncLoopError,
    _append_sync_roadmap_summary,
    _build_items_from_git,
    _extract_progress_roadmap_path,
    _parse_git_status_line,
    _parse_items_file,
    run_sync_loop,
)


def test_parse_items_file_returns_normalized_rows(tmp_path: Path):
    source = tmp_path / "items.json"
    source.write_text(
        json.dumps(
            [
                {
                    "title": "sync commit feature",
                    "summary": "finalize sync commit endpoint",
                    "files": ["api/sync_router.py", "tests/api/test_sync_router.py"],
                    "tags": ["feature", "sync"],
                }
            ]
        ),
        encoding="utf-8",
    )

    rows = _parse_items_file(str(source))
    assert len(rows) == 1
    assert rows[0]["title"] == "sync commit feature"
    assert rows[0]["files"] == ["api/sync_router.py", "tests/api/test_sync_router.py"]
    assert rows[0]["tags"] == ["feature", "sync"]


def test_run_sync_loop_stops_when_handshake_forbidden():
    calls: list[tuple[str, str, dict]] = []

    def fake_sender(base_url: str, path: str, payload: dict):
        calls.append((base_url, path, payload))
        if path == "/sync/handshake/init":
            return {
                "status": "forbidden",
                "handshake": {"allowed": False, "reason": "WIP limit reached", "code": "WIP_LIMIT_REACHED"},
            }
        raise AssertionError("handshake forbidden case should not call other endpoints")

    result = run_sync_loop(
        base_url="http://127.0.0.1:8090",
        project="sophia",
        intent="new mission",
        request_fn=fake_sender,
    )
    assert result["status"] == "forbidden"
    assert result["recorded_total"] == 0
    assert len(calls) == 1
    assert calls[0][1] == "/sync/handshake/init"


def test_run_sync_loop_runs_progress_commit_reconcile():
    calls: list[str] = []

    def fake_sender(_base_url: str, path: str, _payload: dict):
        calls.append(path)
        if path == "/sync/handshake/init":
            return {"status": "ok", "handshake": {"allowed": True}}
        if path == "/sync/progress":
            return {"status": "ok", "recorded": 1, "skipped": 0}
        if path == "/sync/commit":
            return {"status": "ok", "commit_status": "DONE", "recorded": 1, "skipped": 0}
        if path == "/sync/reconcile":
            return {"status": "ok", "recorded": 0, "skipped_items": []}
        raise AssertionError(f"unexpected path: {path}")

    result = run_sync_loop(
        base_url="http://127.0.0.1:8090",
        project="sophia",
        intent="sync commit route",
        mission_id="wp_sync_001",
        items=[
            {
                "title": "sync commit endpoint",
                "summary": "add commit route",
                "files": ["api/sync_router.py"],
                "tags": ["feature"],
            }
        ],
        commit=True,
        tests_passed=True,
        l2_passed=True,
        request_fn=fake_sender,
    )
    assert result["status"] == "ok"
    assert result["recorded_total"] == 2
    assert result["skipped_total"] == 0
    assert calls == [
        "/sync/handshake/init",
        "/sync/progress",
        "/sync/commit",
        "/sync/reconcile",
    ]


def test_parse_git_status_line_handles_rename():
    parsed = _parse_git_status_line("R  old/path/file.md -> new/path/file.md")
    assert parsed == ("R", "new/path/file.md")


def test_build_items_from_git_groups_paths():
    rows = _build_items_from_git(
        changes=[
            ("M", "api/sync_router.py"),
            ("M", "core/forest/canopy.py"),
            ("M", "apps/desktop/src/pages/ReportPage.tsx"),
            ("M", "docs/forest_status_workflow.md"),
        ],
        intent="sync loop strengthen",
        max_items=10,
        tracked_only=False,
    )
    assert rows
    keys = {row["tags"][1] for row in rows if len(row.get("tags", [])) >= 2}
    assert "bucket:api" in keys
    assert "bucket:core" in keys
    assert "bucket:ui" in keys
    assert "bucket:docs" in keys


def test_build_items_from_git_tracks_only_system_categories_by_default():
    rows = _build_items_from_git(
        changes=[
            ("M", "api/sync_router.py"),
            ("M", "apps/desktop/src/pages/ReportPage.tsx"),
            ("M", "docs/forest_status_workflow.md"),
        ],
        intent="tracked only",
        max_items=10,
    )
    assert rows
    categories = {str(row.get("category", "")) for row in rows}
    assert categories == {"SYSTEM_CHANGE"}
    assert all("bucket:api" in row.get("tags", []) for row in rows)


def test_run_sync_loop_auto_prefix_fallback_to_api_sync():
    calls: list[str] = []

    def fake_sender(_base_url: str, path: str, _payload: dict):
        calls.append(path)
        if path == "/sync/handshake/init":
            raise SyncLoopError("http 404 /sync/handshake/init: {'detail': 'Not Found'}")
        if path == "/api/sync/handshake/init":
            return {"status": "ok", "handshake": {"allowed": True}}
        if path == "/api/sync/progress":
            return {"status": "ok", "recorded": 1, "skipped": 0}
        if path == "/api/sync/reconcile":
            return {"status": "ok", "recorded": 0, "skipped_items": []}
        raise AssertionError(f"unexpected path: {path}")

    result = run_sync_loop(
        base_url="http://127.0.0.1:8090",
        project="sophia",
        intent="auto prefix fallback",
        request_fn=fake_sender,
    )
    assert result["status"] == "ok"
    assert result["sync_prefix"] == "/api/sync"
    assert calls[:2] == ["/sync/handshake/init", "/api/sync/handshake/init"]


def test_run_sync_loop_auto_prefix_reports_when_routes_missing():
    def fake_sender(_base_url: str, path: str, _payload: dict):
        raise SyncLoopError(f"http 404 {path}: {{'detail': 'Not Found'}}")

    try:
        run_sync_loop(
            base_url="http://127.0.0.1:8090",
            project="sophia",
            intent="auto prefix missing",
            request_fn=fake_sender,
            get_fn=lambda _base_url, _path: {"status": "error"},
        )
        raise AssertionError("expected SyncLoopError")
    except SyncLoopError as exc:
        text = str(exc)
        assert "sync routes not found on server" in text
        assert "/sync/handshake/init" in text
        assert "/api/sync/handshake/init" in text


def test_run_sync_loop_legacy_mode_when_sync_routes_missing():
    calls: list[str] = []

    def fake_sender(_base_url: str, path: str, _payload: dict):
        calls.append(path)
        if path in {"/sync/handshake/init", "/api/sync/handshake/init"}:
            raise SyncLoopError(f"http 404 {path}: {{'detail': 'Not Found'}}")
        if path == "/forest/projects/sophia/roadmap/sync":
            return {"status": "ok", "recorded": 1, "skipped": 0}
        if path == "/forest/projects/sophia/roadmap/record":
            return {"status": "ok", "path": "/tmp/roadmap_journal.jsonl"}
        raise AssertionError(f"unexpected path: {path}")

    def fake_getter(_base_url: str, path: str):
        assert path == "/openapi.json"
        return {
            "paths": {
                "/forest/projects/{project_name}/roadmap/sync": {},
                "/forest/projects/{project_name}/roadmap/record": {},
            }
        }

    result = run_sync_loop(
        base_url="http://127.0.0.1:8090",
        project="sophia",
        intent="legacy fallback",
        items=[{"title": "legacy sync item", "summary": "", "files": [], "tags": []}],
        request_fn=fake_sender,
        get_fn=fake_getter,
    )
    assert result["status"] == "ok"
    assert result["mode"] == "legacy"
    assert result["legacy_variant"] == "roadmap"
    assert result["sync_prefix"] == "legacy"
    assert "/forest/projects/sophia/roadmap/sync" in calls
    assert "/forest/projects/sophia/roadmap/record" in calls


def test_run_sync_loop_legacy_status_mode_when_only_status_sync_exists():
    calls: list[str] = []

    def fake_sender(_base_url: str, path: str, _payload: dict):
        calls.append(path)
        if path in {"/sync/handshake/init", "/api/sync/handshake/init"}:
            raise SyncLoopError(f"http 404 {path}: {{'detail': 'Not Found'}}")
        if path.startswith("/forest/projects/sophia/status/sync"):
            return {"status": "ok", "summary": {"remaining_work": 3}}
        raise AssertionError(f"unexpected path: {path}")

    def fake_getter(_base_url: str, path: str):
        assert path == "/openapi.json"
        return {
            "paths": {
                "/forest/projects/{project_name}/status/sync": {},
            }
        }

    result = run_sync_loop(
        base_url="http://127.0.0.1:8090",
        project="sophia",
        intent="legacy status fallback",
        items=[{"title": "legacy status sync item", "summary": "", "files": [], "tags": []}],
        request_fn=fake_sender,
        get_fn=fake_getter,
    )
    assert result["status"] == "ok"
    assert result["mode"] == "legacy"
    assert result["legacy_variant"] == "status"
    assert result["sync_prefix"] == "legacy"
    assert calls[0] == "/sync/handshake/init"
    assert calls[1] == "/api/sync/handshake/init"
    assert any(path.startswith("/forest/projects/sophia/status/sync") for path in calls)


def test_extract_progress_roadmap_path_prefers_reconcile_then_progress():
    result = {
        "steps": {
            "progress": {"progress_roadmap_path": "/tmp/progress.md"},
            "reconcile": {"progress_roadmap_path": "/tmp/reconcile.md"},
        }
    }
    assert _extract_progress_roadmap_path(result) == "/tmp/reconcile.md"


def test_append_sync_roadmap_summary_writes_block(tmp_path: Path):
    roadmap = tmp_path / "progress_roadmap.md"
    roadmap.write_text("# title\n", encoding="utf-8")
    result = {
        "sync_prefix": "legacy",
        "mode": "legacy",
        "legacy_variant": "status",
        "recorded_total": 4,
        "skipped_total": 1,
    }
    appended = _append_sync_roadmap_summary(
        roadmap_path=str(roadmap),
        intent="sync smoke",
        result=result,
    )
    assert appended["appended"] is True
    text = roadmap.read_text(encoding="utf-8")
    assert "### Sync Log " in text
    assert "<details>" in text
    assert "intent: sync smoke" in text
    assert "recorded/skipped: 4/1" in text
