import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import chat_router, work_router
from core.forest import layout as forest_layout
from core.memory.schema import create_session_factory


def _client(tmp_path, monkeypatch) -> tuple[TestClient, Path]:
    db_url = f"sqlite:///{tmp_path / 'work_packages.db'}"
    session_factory = create_session_factory(db_url)
    chat_router.session_factory = session_factory
    work_router.session_factory = session_factory
    chat_router._legacy_backfilled = True
    forest_root = tmp_path / "forest" / "project"
    monkeypatch.setattr(forest_layout, "FOREST_ROOT", forest_root)
    app = FastAPI()
    app.include_router(chat_router.router)
    app.include_router(work_router.router)
    return TestClient(app), forest_root


def _load_ledger_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _create_package(client: TestClient):
    res = client.post(
        "/work/packages",
        json={
            "kind": "IMPLEMENT",
            "context_tag": "work",
            "linked_node": "forest:phase3",
            "acceptance_criteria": ["pytest 전체 green", "schema lint 통과"],
            "deliverables": ["tests/api/test_work_router.py", "return_payload.json"],
            "return_payload_spec": {
                "work_package_id": "",
                "status": "DONE | BLOCKED | FAILED",
                "signals": [],
                "artifacts": [],
                "notes": "",
            },
            "title": "Phase-3 Work Packet",
            "description": "manual IDE transfer",
        },
    )
    assert res.status_code == 200
    return res.json()["package"]


def test_work_package_packet_and_lifecycle(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    package = _create_package(client)
    package_id = package["id"]

    assert package["status"] == "READY"
    assert package["work_packet"]["id"] == package_id
    assert package["work_packet"]["kind"] == "IMPLEMENT"
    assert package["work_packet"]["context_tag"] == "work"
    assert "Acceptance Criteria" in package["packet_text"]

    packet_res = client.get(f"/work/packages/{package_id}/packet")
    assert packet_res.status_code == 200
    packet = packet_res.json()
    assert packet["work_package_id"] == package_id
    assert packet["packet"]["kind"] == "IMPLEMENT"
    assert package_id in packet["packet_text"]

    # Ready creation should insert a system notice in work context.
    work_history = client.get("/chat/history", params={"context_tag": "work"}).json()
    assert any("IDE 작업 패킷이 준비되었습니다." in row["content"] for row in work_history)

    ack_res = client.post(f"/work/packages/{package_id}/ack")
    assert ack_res.status_code == 200
    assert ack_res.json()["package"]["status"] == "IN_PROGRESS"

    complete_res = client.post(f"/work/packages/{package_id}/complete")
    assert complete_res.status_code == 200
    assert complete_res.json()["package"]["status"] == "DONE"


def test_submit_report_updates_questions_and_status(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    package = _create_package(client)
    package_id = package["id"]

    report_res = client.post(
        f"/work/packages/{package_id}/report",
        json={
            "work_package_id": package_id,
            "status": "BLOCKED",
            "signals": [
                {
                    "cluster_id": "dependency_missing",
                    "risk_score": 0.82,
                    "evidence": "module dependency path missing",
                }
            ],
            "artifacts": ["logs/report.txt"],
            "notes": "waiting for decision",
        },
    )
    assert report_res.status_code == 200
    body = report_res.json()
    assert body["package"]["status"] == "BLOCKED"
    assert isinstance(body["pending_question_messages"], list)

    pool_rows = client.get("/chat/questions/pool").json()
    target = next(row for row in pool_rows if row["cluster_id"] == "dependency_missing")
    assert target["hit_count"] >= 1
    assert float(target["risk_score"]) >= 0.82
    assert len(target["evidence"]) >= 1

    history = client.get("/chat/history", params={"context_tag": "work"}).json()
    assert any("IDE 완료 보고" in row["content"] for row in history)


def test_report_reanalysis_debounced_and_deduped(tmp_path, monkeypatch):
    client, forest_root = _client(tmp_path, monkeypatch)
    package = _create_package(client)
    package_id = package["id"]

    payload = {
        "work_package_id": package_id,
        "status": "FAILED",
        "signals": [{"cluster_id": "scope_ambiguity", "risk_score": 0.8, "evidence": "missing scope"}],
        "artifacts": [],
        "notes": "first report",
    }
    first = client.post(f"/work/packages/{package_id}/report", json=payload)
    assert first.status_code == 200
    assert first.json()["reanalysis_ran"] is True
    assert first.json()["reanalysis_skip_reason"] == ""
    assert first.json()["canopy_exported"] is True

    dashboard_path = forest_root / "sophia" / "dashboard" / "index.html"
    assert dashboard_path.exists()
    first_mtime = dashboard_path.stat().st_mtime_ns

    ledger_path = forest_root / "sophia" / "ledger" / "ledger.jsonl"
    first_rows = _load_ledger_rows(ledger_path)
    first_types = [row.get("event_type") for row in first_rows]
    assert "WORK_PACKAGE_REPORTED" in first_types
    assert "GROVE_ANALYZED" in first_types
    assert "CANOPY_EXPORTED" in first_types
    first_canopy_count = first_types.count("CANOPY_EXPORTED")

    second = client.post(f"/work/packages/{package_id}/report", json=payload)
    assert second.status_code == 200
    assert second.json()["reanalysis_ran"] is False
    assert second.json()["reanalysis_skip_reason"] in {"debounced_2s", "duplicate_report_hash", "duplicate_report_hash+debounced_2s"}
    assert second.json()["canopy_exported"] is False

    second_mtime = dashboard_path.stat().st_mtime_ns
    assert second_mtime == first_mtime

    second_rows = _load_ledger_rows(ledger_path)
    second_types = [row.get("event_type") for row in second_rows]
    assert second_types.count("CANOPY_EXPORTED") == first_canopy_count


def test_report_auto_sync_runs_once_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setattr(work_router.settings, "forest_auto_sync", True, raising=False)
    client, forest_root = _client(tmp_path, monkeypatch)
    package = _create_package(client)
    package_id = package["id"]

    payload = {
        "work_package_id": package_id,
        "status": "BLOCKED",
        "signals": [{"cluster_id": "scope_ambiguity", "risk_score": 0.8, "evidence": "missing scope"}],
        "artifacts": [],
        "notes": "auto sync first report",
    }
    first = client.post(f"/work/packages/{package_id}/report", json=payload)
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["reanalysis_ran"] is True
    assert first_body["reanalysis_skip_reason"] == ""
    assert first_body["auto_sync_enabled"] is True
    assert first_body["auto_sync_ran"] is True
    assert first_body["progress_snapshot_path"]
    assert first_body["progress_roadmap_path"]

    progress_snapshot = forest_root / "sophia" / "status" / "progress_snapshot.json"
    progress_roadmap = forest_root / "sophia" / "status" / "progress_roadmap.md"
    assert progress_snapshot.exists()
    assert progress_roadmap.exists()

    ledger_path = forest_root / "sophia" / "ledger" / "ledger.jsonl"
    first_rows = _load_ledger_rows(ledger_path)
    first_status_synced = [row for row in first_rows if row.get("event_type") == "STATUS_SYNCED"]
    assert len(first_status_synced) == 1

    second = client.post(f"/work/packages/{package_id}/report", json=payload)
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["reanalysis_ran"] is False
    assert second_body["reanalysis_skip_reason"] in {"debounced_2s", "duplicate_report_hash", "duplicate_report_hash+debounced_2s"}
    assert second_body["auto_sync_enabled"] is True
    assert second_body["auto_sync_ran"] is False

    second_rows = _load_ledger_rows(ledger_path)
    second_status_synced = [row for row in second_rows if row.get("event_type") == "STATUS_SYNCED"]
    assert len(second_status_synced) == 1


def test_work_create_blocked_by_focus_lock_when_wip_limit_reached(tmp_path, monkeypatch):
    monkeypatch.setattr(work_router.settings, "forest_focus_mode", True, raising=False)
    monkeypatch.setattr(work_router.settings, "forest_focus_lock_level", "soft", raising=False)
    monkeypatch.setattr(work_router.settings, "forest_wip_limit", 1, raising=False)
    client, _ = _client(tmp_path, monkeypatch)

    first = _create_package(client)
    package_id = first["id"]
    ack_res = client.post(f"/work/packages/{package_id}/ack")
    assert ack_res.status_code == 200
    assert ack_res.json()["package"]["status"] == "IN_PROGRESS"

    second_res = client.post(
        "/work/packages",
        json={
            "kind": "REVIEW",
            "context_tag": "work",
            "linked_node": "forest:phase4",
            "title": "Second Package",
            "description": "should be blocked by focus lock",
        },
    )
    assert second_res.status_code == 409
    detail = second_res.json().get("detail", {})
    assert detail.get("code") == "FOCUS_LOCKED"
    assert detail.get("reason", "").startswith("WIP_LIMIT_REACHED")


def test_work_create_allowed_in_soft_lock_when_under_wip_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(work_router.settings, "forest_focus_mode", True, raising=False)
    monkeypatch.setattr(work_router.settings, "forest_focus_lock_level", "soft", raising=False)
    monkeypatch.setattr(work_router.settings, "forest_wip_limit", 2, raising=False)
    client, _ = _client(tmp_path, monkeypatch)

    first = _create_package(client)
    ack_res = client.post(f"/work/packages/{first['id']}/ack")
    assert ack_res.status_code == 200
    assert ack_res.json()["package"]["status"] == "IN_PROGRESS"

    second_res = client.post(
        "/work/packages",
        json={
            "kind": "REVIEW",
            "context_tag": "work",
            "linked_node": "forest:phase4",
            "title": "Second Package",
            "description": "soft lock should allow while under limit",
        },
    )
    assert second_res.status_code == 200
    assert second_res.json()["package"]["status"] == "READY"


def test_work_create_blocked_in_hard_lock_even_with_higher_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(work_router.settings, "forest_focus_mode", True, raising=False)
    monkeypatch.setattr(work_router.settings, "forest_focus_lock_level", "hard", raising=False)
    monkeypatch.setattr(work_router.settings, "forest_wip_limit", 3, raising=False)
    client, _ = _client(tmp_path, monkeypatch)

    first = _create_package(client)
    ack_res = client.post(f"/work/packages/{first['id']}/ack")
    assert ack_res.status_code == 200
    assert ack_res.json()["package"]["status"] == "IN_PROGRESS"

    second_res = client.post(
        "/work/packages",
        json={
            "kind": "REVIEW",
            "context_tag": "work",
            "linked_node": "forest:phase4",
            "title": "Second Package",
            "description": "hard lock should block any new creation while active mission exists",
        },
    )
    assert second_res.status_code == 409
    detail = second_res.json().get("detail", {})
    assert detail.get("code") == "FOCUS_LOCKED"
    assert detail.get("reason", "").startswith("HARD_LOCK_ACTIVE")


def test_work_lifecycle_records_live_roadmap_journal(tmp_path, monkeypatch):
    client, forest_root = _client(tmp_path, monkeypatch)
    package = _create_package(client)
    package_id = package["id"]

    ack_res = client.post(f"/work/packages/{package_id}/ack")
    assert ack_res.status_code == 200

    report_res = client.post(
        f"/work/packages/{package_id}/report",
        json={
            "work_package_id": package_id,
            "status": "BLOCKED",
            "signals": [
                {
                    "cluster_id": "scope_ambiguity",
                    "risk_score": 0.84,
                    "evidence": "missing scope detail",
                }
            ],
            "artifacts": [],
            "notes": "waiting for decision",
        },
    )
    assert report_res.status_code == 200

    journal_path = forest_root / "sophia" / "status" / "roadmap_journal.jsonl"
    assert journal_path.exists()

    rows = _load_ledger_rows(journal_path)
    live_rows = [row for row in rows if str(row.get("type", "")).strip().upper() == "LIVE_EVENT"]
    assert len(live_rows) >= 2
    categories = {str(row.get("category", "")).strip().upper() for row in live_rows}
    assert categories.intersection({"FEATURE_ADD", "SYSTEM_CHANGE", "PROBLEM_FIX"})
    assert any(str(row.get("title", "")).startswith("[work]") for row in live_rows)
