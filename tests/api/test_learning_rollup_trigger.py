from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import chat_router, forest_router
from core.forest import layout as forest_layout
from core.memory.schema import MindLearningRollup, create_session_factory
from sophia_kernel.modules.mind_diary import ingest_trigger_event


def _build_client(tmp_path, monkeypatch) -> TestClient:
    db_url = f"sqlite:///{tmp_path / 'learning_rollup_trigger.db'}"
    session_factory = create_session_factory(db_url)
    chat_router.session_factory = session_factory
    forest_router.session_factory = session_factory
    chat_router._legacy_backfilled = True
    monkeypatch.setattr(forest_layout, "FOREST_ROOT", tmp_path / "forest" / "project")

    app = FastAPI()
    app.include_router(chat_router.router)
    app.include_router(forest_router.router)
    return TestClient(app)


def test_rollup_updates_on_ingest_trigger_event(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'rollup_ingest.db'}"
    session_factory = create_session_factory(db_url)
    session = session_factory()
    try:
        payload = {
            "term": "작업",
            "meaning": "에디터 분석",
            "confidence": 0.7,
            "trace_id": "trace_rollup_same",
        }
        ingest_trigger_event(session, event_type="TERM_MAPPING", payload=payload)
        ingest_trigger_event(session, event_type="TERM_MAPPING", payload=payload)
        session.commit()

        total_row = (
            session.query(MindLearningRollup)
            .filter(MindLearningRollup.rollup_type == "TOTAL", MindLearningRollup.bucket_key == "all")
            .one_or_none()
        )
        assert total_row is not None
        tracked = total_row.payload.get("tracked_events", {})
        assert tracked.get("TERM_MAPPING", 0) == 1
    finally:
        session.close()


def test_canopy_prefers_rollup_after_chat_without_canopy_call(tmp_path, monkeypatch):
    client = _build_client(tmp_path, monkeypatch)

    for text in ("ping", "smoke test", "안녕", "ping", "smoke test"):
        res = client.post(
            "/chat/messages",
            json={
                "role": "user",
                "content": text,
                "context_tag": "chat",
                "importance": 0.5,
                "status": "normal",
            },
        )
        assert res.status_code == 200

    session = chat_router.session_factory()
    try:
        total_row = (
            session.query(MindLearningRollup)
            .filter(MindLearningRollup.rollup_type == "TOTAL", MindLearningRollup.bucket_key == "all")
            .one_or_none()
        )
        assert total_row is not None
        assert int(total_row.source_event_count or 0) > 0
    finally:
        session.close()

    canopy = client.get("/forest/projects/sophia/canopy/data")
    assert canopy.status_code == 200
    body = canopy.json()
    assert "learning_summary" not in body
    assert "module_overview" in body
    assert "roadmap" in body
