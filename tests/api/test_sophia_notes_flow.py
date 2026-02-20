from datetime import datetime, UTC

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import chat_router, forest_router, memory_router, work_router
from core.forest import layout as forest_layout
from core.memory.schema import create_session_factory


def _build_client(tmp_path, monkeypatch) -> tuple[TestClient, str]:
    db_url = f"sqlite:///{tmp_path / 'sophia_notes.db'}"
    session_factory = create_session_factory(db_url)
    chat_router.session_factory = session_factory
    work_router.session_factory = session_factory
    forest_router.session_factory = session_factory
    memory_router._SessionLocal = session_factory
    chat_router._legacy_backfilled = True

    monkeypatch.setattr(forest_layout, "FOREST_ROOT", tmp_path / "forest" / "project")

    app = FastAPI()
    app.include_router(chat_router.router)
    app.include_router(work_router.router)
    app.include_router(forest_router.router)
    app.include_router(memory_router.router)
    return TestClient(app), datetime.now(UTC).date().isoformat()


def test_work_report_creates_system_note(tmp_path, monkeypatch):
    client, today = _build_client(tmp_path, monkeypatch)

    package = client.post(
        "/work/packages",
        json={
            "kind": "IMPLEMENT",
            "context_tag": "work",
            "linked_node": "auth-module",
            "acceptance_criteria": ["test"],
            "deliverables": ["x"],
            "title": "Work package for note",
        },
    ).json()["package"]

    report_res = client.post(
        f"/work/packages/{package['id']}/report",
        json={
            "work_package_id": package["id"],
            "status": "DONE",
            "signals": [{"cluster_id": "scope_ambiguity", "risk_score": 0.63, "evidence": "scope note"}],
            "artifacts": ["artifact.txt"],
            "notes": "report complete",
        },
    )
    assert report_res.status_code == 200

    notes_res = client.get("/memory/notes", params={"date": today})
    assert notes_res.status_code == 200
    items = notes_res.json()["items"]
    assert any(item["note_type"] == "WORK_REPORT_DIGEST" for item in items)


def test_grove_analyze_creates_system_note(tmp_path, monkeypatch):
    client, today = _build_client(tmp_path, monkeypatch)
    init_res = client.post("/forest/projects/init", json={"project_name": "sophia"})
    assert init_res.status_code == 200

    analyze_res = client.post(
        "/forest/projects/sophia/grove/analyze",
        json={
            "doc_name": "spec_v2.md",
            "content": "로그인 설계 범위가 아직 모호합니다.",
            "target": "auth-module",
            "change": "로그인 로직 수정",
        },
    )
    assert analyze_res.status_code == 200

    notes_res = client.get("/memory/notes", params={"date": today})
    items = notes_res.json()["items"]
    assert any(item["note_type"] == "GROVE_SUMMARY" for item in items)


def test_linked_cluster_response_creates_system_note(tmp_path, monkeypatch):
    client, today = _build_client(tmp_path, monkeypatch)

    signal_res = client.post(
        "/chat/questions/signal",
        json={
            "cluster_id": "scope_ambiguity",
            "description": "범위 불명확",
            "risk_score": 0.82,
        },
    )
    assert signal_res.status_code == 200

    msg_res = client.post(
        "/chat/messages",
        json={
            "role": "user",
            "content": "적용 범위를 명시했고 결정했습니다.",
            "context_tag": "question-queue",
            "linked_cluster": "scope_ambiguity",
        },
    )
    assert msg_res.status_code == 200

    notes_res = client.get("/memory/notes", params={"date": today})
    items = notes_res.json()["items"]
    assert any(item["note_type"] == "QUESTION_RESPONSE_DIGEST" for item in items)

    status_res = client.get("/memory/notes/status")
    assert status_res.status_code == 200
    status = status_res.json()
    assert "generator_status" in status
    assert "last_generated_at" in status
