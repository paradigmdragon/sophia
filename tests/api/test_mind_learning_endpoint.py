from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import mind_router
from core.memory.schema import create_session_factory


def _build_client(tmp_path) -> TestClient:
    db_url = f"sqlite:///{tmp_path / 'mind_learning.db'}"
    session_factory = create_session_factory(db_url)
    mind_router._SessionLocal = session_factory
    app = FastAPI()
    app.include_router(mind_router.router)
    return TestClient(app)


def test_learning_endpoint_returns_rollup_summary(tmp_path):
    client = _build_client(tmp_path)

    events = [
        ("UNCONSCIOUS_HIT", {"pattern_id": "PING_OK", "trace_id": "trace_1"}),
        ("USER_PREFERENCE", {"key": "response_tone", "value": "짧게", "trace_id": "trace_2"}),
        ("TOPIC_SEEN", {"topic": "epidora", "count": 3, "trace_id": "trace_3"}),
    ]
    for event_type, payload in events:
        response = client.post("/mind/trigger", json={"event_type": event_type, "payload": payload})
        assert response.status_code == 200

    result = client.get("/mind/learning")
    assert result.status_code == 200
    body = result.json()

    assert body["status"] == "ok"
    assert body["growth_stage"] in {"SEED", "SPROUT", "GROWING"}
    assert int(body["total_tracked_events"]) >= 3
    tracked = body.get("tracked_events", {})
    assert int(tracked.get("UNCONSCIOUS_HIT", 0)) >= 1
    assert int(tracked.get("USER_PREFERENCE", 0)) >= 1
    assert int(tracked.get("TOPIC_SEEN", 0)) >= 1
    assert "rollups" in body
    assert body["rollups"]["total"].get("rollup_type") == "TOTAL"
