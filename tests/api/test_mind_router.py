from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import chat_router, forest_router, mind_router, work_router
from core.forest import layout as forest_layout
from core.memory.schema import create_session_factory


def _build_client(tmp_path, monkeypatch) -> TestClient:
    db_url = f"sqlite:///{tmp_path / 'mind_api.db'}"
    session_factory = create_session_factory(db_url)
    chat_router.session_factory = session_factory
    work_router.session_factory = session_factory
    forest_router.session_factory = session_factory
    mind_router._SessionLocal = session_factory
    chat_router._legacy_backfilled = True

    monkeypatch.setattr(forest_layout, "FOREST_ROOT", tmp_path / "forest" / "project")

    app = FastAPI()
    app.include_router(chat_router.router)
    app.include_router(work_router.router)
    app.include_router(forest_router.router)
    app.include_router(mind_router.router)
    return TestClient(app)


def test_work_package_created_triggers_task_mind_item(tmp_path, monkeypatch):
    client = _build_client(tmp_path, monkeypatch)

    res = client.post(
        "/work/packages",
        json={
            "kind": "IMPLEMENT",
            "context_tag": "work",
            "linked_node": "auth-module",
            "acceptance_criteria": ["test"],
            "deliverables": ["x"],
            "title": "Mind Task Seed",
        },
    )
    assert res.status_code == 200

    dashboard = client.get("/mind/dashboard")
    assert dashboard.status_code == 200
    items = dashboard.json()["items"]
    assert any(item["type"] == "TASK" for item in items)


def test_question_ready_triggers_question_cluster_item(tmp_path, monkeypatch):
    client = _build_client(tmp_path, monkeypatch)

    for _ in range(3):
        res = client.post(
            "/chat/questions/signal",
            json={
                "cluster_id": "scope_ambiguity",
                "description": "범위 불명확",
                "risk_score": 0.72,
            },
        )
        assert res.status_code == 200

    dashboard = client.get("/mind/dashboard")
    assert dashboard.status_code == 200
    items = dashboard.json()["items"]
    assert any(item["type"] == "QUESTION_CLUSTER" and "scope_ambiguity" in item["id"] for item in items)


def test_grove_analyzed_with_signals_creates_alert_item(tmp_path, monkeypatch):
    client = _build_client(tmp_path, monkeypatch)
    init_res = client.post("/forest/projects/init", json={"project_name": "sophia"})
    assert init_res.status_code == 200

    analyze = client.post(
        "/forest/projects/sophia/grove/analyze",
        json={
            "doc_name": "spec.md",
            "content": "범위가 모호하고 dependency 가 누락됨",
            "target": "auth-module",
            "change": "로그인 변경",
        },
    )
    assert analyze.status_code == 200

    dashboard = client.get("/mind/dashboard")
    items = dashboard.json()["items"]
    assert any(item["type"] == "ALERT" for item in items)


def test_mind_adjust_actions(tmp_path, monkeypatch):
    client = _build_client(tmp_path, monkeypatch)
    seed = client.post(
        "/mind/trigger",
        json={
            "event_type": "WORK_PACKAGE_CREATED",
            "payload": {"id": "wp_seed_001", "kind": "IMPLEMENT", "context_tag": "work"},
        },
    )
    assert seed.status_code == 200

    items_res = client.get("/mind/items")
    assert items_res.status_code == 200
    items = items_res.json()["items"]
    target = next(item for item in items if item["id"] == "task:wp_seed_001")

    pin = client.post(f"/mind/items/{target['id']}/pin")
    assert pin.status_code == 200
    assert pin.json()["item"]["priority"] == 100

    park = client.post(f"/mind/items/{target['id']}/park")
    assert park.status_code == 200
    assert park.json()["item"]["status"] == "parked"

    done = client.post(f"/mind/items/{target['id']}/done")
    assert done.status_code == 200
    assert done.json()["item"]["status"] == "done"
