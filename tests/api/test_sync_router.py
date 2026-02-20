from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import forest_router, sync_router
from core.forest import layout as forest_layout
from core.memory.schema import WorkPackage, create_session_factory


def _build_client(tmp_path, monkeypatch) -> tuple[TestClient, Path, Any]:
    db_url = f"sqlite:///{tmp_path / 'sync_router.db'}"
    session_factory = create_session_factory(db_url)
    forest_router.session_factory = session_factory
    sync_router.session_factory = session_factory

    forest_root = tmp_path / "forest" / "project"
    monkeypatch.setattr(forest_layout, "FOREST_ROOT", forest_root)
    monkeypatch.setattr(forest_router, "BASE_DIR", tmp_path)
    monkeypatch.setattr(forest_router, "WORKSPACE_ROOT", tmp_path / "workspace")
    monkeypatch.setattr(forest_router, "SOPHIA_WORKSPACE_ROOT", tmp_path / "sophia_workspace")

    app = FastAPI()
    app.include_router(forest_router.router)
    app.include_router(sync_router.router)
    return TestClient(app), forest_root, session_factory


def test_sync_handshake_allows_when_no_active(tmp_path, monkeypatch):
    client, _, _ = _build_client(tmp_path, monkeypatch)
    assert client.post("/forest/projects/init", json={"project_name": "sophia"}).status_code == 200

    response = client.post(
        "/sync/handshake/init",
        json={"project_name": "sophia", "intent": "login auth 구현 진행"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["handshake"]["allowed"] is True
    assert body["handshake"]["code"] == "OK"


def test_sync_handshake_blocks_when_wip_reached(tmp_path, monkeypatch):
    client, _, session_factory = _build_client(tmp_path, monkeypatch)
    assert client.post("/forest/projects/init", json={"project_name": "sophia"}).status_code == 200

    now = datetime.now(UTC)
    session = session_factory()
    try:
        session.add(
            WorkPackage(
                id="wp_active_1",
                title="active mission",
                description="sync test",
                payload={"work_packet": {"kind": "IMPLEMENT", "context_tag": "work"}, "project": "sophia"},
                context_tag="work",
                status="IN_PROGRESS",
                linked_node="forest:canopy",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.post(
        "/sync/handshake/init",
        json={"project_name": "sophia", "intent": "another feature 시작"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "forbidden"
    assert body["handshake"]["allowed"] is False
    assert body["handshake"]["code"] == "WIP_LIMIT_REACHED"


def test_sync_handshake_override_allows_second_active(tmp_path, monkeypatch):
    client, _, session_factory = _build_client(tmp_path, monkeypatch)
    assert client.post("/forest/projects/init", json={"project_name": "sophia"}).status_code == 200

    now = datetime.now(UTC)
    session = session_factory()
    try:
        session.add(
            WorkPackage(
                id="wp_active_1",
                title="active mission",
                description="sync test",
                payload={"work_packet": {"kind": "IMPLEMENT", "context_tag": "work"}, "project": "sophia"},
                context_tag="work",
                status="IN_PROGRESS",
                linked_node="forest:canopy",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.post(
        "/sync/handshake/init",
        json={"project_name": "sophia", "intent": "긴급 hotfix 시작", "override_token": "approved-by-user"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["handshake"]["allowed"] is True


def test_sync_progress_records_only_meaningful_categories(tmp_path, monkeypatch):
    client, _, _ = _build_client(tmp_path, monkeypatch)
    assert client.post("/forest/projects/init", json={"project_name": "sophia"}).status_code == 200

    response = client.post(
        "/sync/progress",
        json={
            "project_name": "sophia",
            "mission_id": "wp_active_1",
            "progress_note": "중간 진행 보고",
            "items": [
                {
                    "title": "work policy bug fix",
                    "summary": "focus lock 누락 수정",
                    "files": ["api/work_router.py"],
                    "tags": ["fix"],
                },
                {
                    "title": "detail panel spacing",
                    "summary": "ui 정렬 변경",
                    "files": ["apps/desktop/src/pages/report/DetailPanel.tsx"],
                    "tags": ["ui"],
                },
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["recorded"] == 1
    assert body["skipped"] == 1
    assert body["recorded_items"][0]["category"] in {"PROBLEM_FIX", "FEATURE_ADD", "SYSTEM_CHANGE"}
    assert body["skipped_items"][0]["reason"].startswith("policy_skip")

    journal_path = Path(body["path"])
    assert journal_path.exists()
    lines = [line for line in journal_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 1
    assert sum(1 for line in lines if "\"type\": \"SYNC_PROGRESS\"" in line) == 1


def test_sync_progress_deduplicates_same_payload(tmp_path, monkeypatch):
    client, _, _ = _build_client(tmp_path, monkeypatch)
    assert client.post("/forest/projects/init", json={"project_name": "sophia"}).status_code == 200
    payload = {
        "project_name": "sophia",
        "items": [
            {
                "title": "sync handshake feature add",
                "summary": "sync progress endpoint 추가",
                "files": ["api/sync_router.py"],
                "tags": ["feature"],
            }
        ],
    }
    first = client.post("/sync/progress", json=payload)
    assert first.status_code == 200
    assert first.json()["recorded"] == 1

    second = client.post("/sync/progress", json=payload)
    assert second.status_code == 200
    body = second.json()
    assert body["recorded"] == 0
    assert body["skipped"] == 1
    assert body["skipped_items"][0]["reason"] == "duplicate"


def test_sync_commit_updates_work_done_and_records(tmp_path, monkeypatch):
    client, _, session_factory = _build_client(tmp_path, monkeypatch)
    assert client.post("/forest/projects/init", json={"project_name": "sophia"}).status_code == 200

    now = datetime.now(UTC)
    session = session_factory()
    try:
        session.add(
            WorkPackage(
                id="wp_commit_done",
                title="commit target",
                description="sync commit test",
                payload={"work_packet": {"kind": "IMPLEMENT", "context_tag": "work"}, "project": "sophia"},
                context_tag="work",
                status="IN_PROGRESS",
                linked_node="forest:canopy",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.post(
        "/sync/commit",
        json={
            "project_name": "sophia",
            "mission_id": "wp_commit_done",
            "final_summary": "핵심 기능 완료",
            "validation": {"tests_passed": True, "l2_passed": True, "proof": ["pytest green"]},
            "items": [
                {
                    "title": "sync commit feature add",
                    "summary": "상태 전이 및 기록 반영",
                    "files": ["api/sync_router.py"],
                    "tags": ["feature"],
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["commit_status"] == "DONE"
    assert body["work"]["status"] == "DONE"
    assert body["recorded"] == 1

    session = session_factory()
    try:
        row = session.query(WorkPackage).filter(WorkPackage.id == "wp_commit_done").first()
        assert row is not None
        assert row.status == "DONE"
        assert row.completed_at is not None
    finally:
        session.close()


def test_sync_commit_updates_work_blocked_on_validation_fail(tmp_path, monkeypatch):
    client, _, session_factory = _build_client(tmp_path, monkeypatch)
    assert client.post("/forest/projects/init", json={"project_name": "sophia"}).status_code == 200

    now = datetime.now(UTC)
    session = session_factory()
    try:
        session.add(
            WorkPackage(
                id="wp_commit_blocked",
                title="commit target blocked",
                description="sync commit test",
                payload={"work_packet": {"kind": "IMPLEMENT", "context_tag": "work"}, "project": "sophia"},
                context_tag="work",
                status="IN_PROGRESS",
                linked_node="forest:canopy",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.post(
        "/sync/commit",
        json={
            "project_name": "sophia",
            "mission_id": "wp_commit_blocked",
            "validation": {"tests_passed": False, "l2_passed": True, "failure_reason": "pytest failed"},
            "items": [
                {
                    "title": "sync commit blocker fix",
                    "summary": "테스트 실패로 BLOCKED",
                    "files": ["api/work_router.py"],
                    "tags": ["fix"],
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["commit_status"] == "BLOCKED"
    assert body["work"]["status"] == "BLOCKED"
    assert body["recorded"] == 1

    session = session_factory()
    try:
        row = session.query(WorkPackage).filter(WorkPackage.id == "wp_commit_blocked").first()
        assert row is not None
        assert row.status == "BLOCKED"
    finally:
        session.close()


def test_sync_reconcile_detects_no_baseline_and_records(tmp_path, monkeypatch):
    client, _, _ = _build_client(tmp_path, monkeypatch)
    assert client.post("/forest/projects/init", json={"project_name": "sophia"}).status_code == 200
    # create one work so current view has mission context
    create = client.post(
        "/forest/projects/sophia/work/generate",
        json={
            "kind": "IMPLEMENT",
            "context_tag": "work",
            "linked_node": "forest:canopy",
            "issue": "reconcile baseline test",
            "required": ["acceptance 정의"],
        },
    )
    assert create.status_code == 200

    response = client.post("/sync/reconcile", json={"project_name": "sophia", "apply": True})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["mismatch_count"] >= 1
    assert any(row["code"] == "NO_BASELINE" for row in body["mismatches"])
    assert body["applied"] is True
    assert body["recorded"] in {0, 1}


def test_sync_reconcile_after_snapshot_has_no_mismatch(tmp_path, monkeypatch):
    client, _, _ = _build_client(tmp_path, monkeypatch)
    assert client.post("/forest/projects/init", json={"project_name": "sophia"}).status_code == 200
    create = client.post(
        "/forest/projects/sophia/work/generate",
        json={
            "kind": "IMPLEMENT",
            "context_tag": "work",
            "linked_node": "forest:canopy",
            "issue": "reconcile aligned test",
            "required": ["acceptance 정의"],
        },
    )
    assert create.status_code == 200
    # baseline snapshot
    snap = client.post("/forest/projects/sophia/roadmap/record", json={"note": "baseline"})
    assert snap.status_code == 200

    response = client.post("/sync/reconcile", json={"project_name": "sophia", "apply": True})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["mismatch_count"] == 0
    assert body["applied"] is False
    assert body["recorded"] == 0


def test_sync_progress_dedupes_from_git_even_when_summary_changes(tmp_path, monkeypatch):
    client, _, _ = _build_client(tmp_path, monkeypatch)
    assert client.post("/forest/projects/init", json={"project_name": "sophia"}).status_code == 200

    first = client.post(
        "/sync/progress",
        json={
            "project_name": "sophia",
            "items": [
                {
                    "title": "api changes (3)",
                    "summary": "intent A · api/chat_router.py, api/server.py",
                    "files": ["api/chat_router.py", "api/server.py"],
                    "tags": ["git-auto", "bucket:api", "category:system_change"],
                    "category": "SYSTEM_CHANGE",
                    "note": "from_git",
                }
            ],
        },
    )
    assert first.status_code == 200
    assert first.json()["recorded"] == 1

    second = client.post(
        "/sync/progress",
        json={
            "project_name": "sophia",
            "items": [
                {
                    "title": "api changes (3)",
                    "summary": "intent B · api/chat_router.py, api/server.py",
                    "files": ["api/chat_router.py", "api/server.py"],
                    "tags": ["git-auto", "bucket:api", "category:system_change"],
                    "category": "SYSTEM_CHANGE",
                    "note": "from_git",
                }
            ],
        },
    )
    assert second.status_code == 200
    body = second.json()
    assert body["recorded"] == 0
    assert body["skipped"] == 1
    assert any(str(row.get("reason", "")) == "duplicate" for row in body.get("skipped_items", []))
