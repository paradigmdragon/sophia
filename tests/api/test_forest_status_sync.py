from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import forest_router
from core.forest import layout as forest_layout
from core.memory.schema import create_session_factory


def _build_client(tmp_path, monkeypatch) -> tuple[TestClient, Path]:
    db_url = f"sqlite:///{tmp_path / 'forest_status_sync.db'}"
    session_factory = create_session_factory(db_url)
    forest_router.session_factory = session_factory

    forest_root = tmp_path / "forest" / "project"
    monkeypatch.setattr(forest_layout, "FOREST_ROOT", forest_root)
    monkeypatch.setattr(forest_router, "BASE_DIR", tmp_path)
    monkeypatch.setattr(forest_router, "WORKSPACE_ROOT", tmp_path / "workspace")
    monkeypatch.setattr(forest_router, "SOPHIA_WORKSPACE_ROOT", tmp_path / "sophia_workspace")

    app = FastAPI()
    app.include_router(forest_router.router)
    return TestClient(app), forest_root


def test_canopy_data_marks_progress_synced_after_project_init(tmp_path, monkeypatch):
    client, _ = _build_client(tmp_path, monkeypatch)
    project = "sophia"
    assert client.post("/forest/projects/init", json={"project_name": project}).status_code == 200

    data = client.get(f"/forest/projects/{project}/canopy/data")
    assert data.status_code == 200
    body = data.json()
    assert body["progress_sync"]["status"] == "synced"
    assert "summary" in body["progress_sync"]


def test_status_sync_writes_progress_files_and_exposes_synced_state(tmp_path, monkeypatch):
    client, forest_root = _build_client(tmp_path, monkeypatch)
    project = "sophia"
    assert client.post("/forest/projects/init", json={"project_name": project}).status_code == 200

    generate = client.post(
        f"/forest/projects/{project}/work/generate",
        json={
            "kind": "IMPLEMENT",
            "context_tag": "work",
            "linked_node": "auth-module",
            "issue": "status sync smoke",
            "required": ["define acceptance"],
            "deliverables": ["return_payload.json"],
        },
    )
    assert generate.status_code == 200

    sync_res = client.post(f"/forest/projects/{project}/status/sync")
    assert sync_res.status_code == 200
    payload = sync_res.json()
    assert payload["status"] == "ok"

    snapshot_path = Path(payload["progress_snapshot_path"])
    roadmap_path = Path(payload["progress_roadmap_path"])
    assert snapshot_path.exists()
    assert roadmap_path.exists()
    assert "다음 실행 항목" in roadmap_path.read_text(encoding="utf-8")

    canopy_data = client.get(f"/forest/projects/{project}/canopy/data")
    assert canopy_data.status_code == 200
    data = canopy_data.json()
    assert data["progress_sync"]["status"] == "synced"
    assert isinstance(data["progress_sync"].get("next_actions", []), list)

    ledger_path = forest_root / project / "ledger" / "ledger.jsonl"
    assert ledger_path.exists()
    text = ledger_path.read_text(encoding="utf-8")
    assert "STATUS_SYNCED" in text
