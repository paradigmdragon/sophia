from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from api import mind_router
from core.memory.schema import create_session_factory


def _build_client(tmp_path) -> tuple[TestClient, str]:
    db_url = f"sqlite:///{tmp_path / 'mind_bitmap.db'}"
    session_factory = create_session_factory(db_url)
    mind_router._SessionLocal = session_factory
    app = FastAPI()
    app.include_router(mind_router.router)
    return TestClient(app), db_url


def _seed_bitmap_tables(db_url: str) -> None:
    session_factory = create_session_factory(db_url)
    session = session_factory()
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    try:
        session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS candidates (
                    candidate_id TEXT PRIMARY KEY,
                    episode_id TEXT,
                    note_thin TEXT,
                    confidence INTEGER,
                    proposed_at TEXT,
                    status TEXT
                )
                """
            )
        )
        session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS backbones (
                    backbone_id TEXT PRIMARY KEY,
                    combined_bits INTEGER,
                    role TEXT,
                    adopted_at TEXT
                )
                """
            )
        )
        session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    type TEXT,
                    payload TEXT,
                    at TEXT
                )
                """
            )
        )

        session.execute(
            text(
                """
                INSERT INTO candidates (candidate_id, episode_id, note_thin, confidence, proposed_at, status)
                VALUES
                  ('cand_1', 'ep_1', 'candidate note', 88, :now, 'REJECTED'),
                  ('cand_2', 'ep_1', 'candidate note2', 72, :now, 'ADOPTED'),
                  ('cand_3', 'ep_2', 'candidate note3', 64, :now, 'PENDING')
                """
            ),
            {"now": now},
        )
        session.execute(
            text(
                """
                INSERT INTO backbones (backbone_id, combined_bits, role, adopted_at)
                VALUES
                  ('bb_1', 4369, 'PRIMARY', :now),
                  ('bb_2', 4369, 'ALT', :now)
                """
            ),
            {"now": now},
        )
        session.execute(
            text(
                """
                INSERT INTO events (event_id, type, payload, at)
                VALUES
                  ('evt_1', 'BITMAP_INVALID', :payload_invalid, :now),
                  ('evt_2', 'CONFLICT_MARK', :payload_conflict, :now),
                  ('evt_3', 'PROPOSE', '{"candidate_id":"cand_3"}', :now),
                  ('evt_4', 'REJECT', '{"candidate_id":"cand_1"}', :now),
                  ('evt_5', 'ADOPT', '{"candidate_id":"cand_2"}', :now)
                """
            ),
            {
                "now": now,
                "payload_invalid": '{"stage":"propose","reason":"INVALID_CHUNK_A","bits_raw":61440}',
                "payload_conflict": '{"rule":"D_EQUIVALENCE_OPPOSITIONAL"}',
            },
        )
        session.commit()
    finally:
        session.close()


def _seed_bitmap_tables_with_episode_events(db_url: str) -> None:
    session_factory = create_session_factory(db_url)
    session = session_factory()
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    try:
        session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS candidates (
                    candidate_id TEXT PRIMARY KEY,
                    episode_id TEXT,
                    note_thin TEXT,
                    confidence INTEGER,
                    proposed_at TEXT,
                    status TEXT
                )
                """
            )
        )
        session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    episode_id TEXT,
                    type TEXT,
                    payload TEXT,
                    at TEXT
                )
                """
            )
        )
        session.execute(
            text(
                """
                INSERT INTO candidates (candidate_id, episode_id, note_thin, confidence, proposed_at, status)
                VALUES ('cand_1', 'ep_1', 'candidate note', 88, :now, 'REJECTED')
                """
            ),
            {"now": now},
        )
        session.execute(
            text(
                """
                INSERT INTO events (event_id, episode_id, type, payload, at)
                VALUES
                  ('evt_right', 'ep_1', 'REJECT', '{"candidate_id":"cand_1","reason":"manual_reject_ui"}', :now),
                  ('evt_wrong', 'ep_2', 'REJECT', '{"candidate_id":"cand_1","reason":"wrong_episode"}', :now)
                """
            ),
            {"now": now},
        )
        session.commit()
    finally:
        session.close()


def test_mind_bitmap_summary_endpoint_returns_metrics(tmp_path):
    client, db_url = _build_client(tmp_path)
    _seed_bitmap_tables(db_url)

    response = client.get("/mind/bitmap")
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "ok"
    assert isinstance(body.get("candidates"), list)
    assert any(str(row.get("episode_id", "")).startswith("ep") for row in body.get("candidates", []))
    assert isinstance(body.get("anchors"), list)
    assert isinstance(body.get("invalid_recent"), list)
    metrics = body.get("metrics", {})
    assert int(metrics.get("candidate_count_7d", 0)) >= 1
    assert int(metrics.get("anchor_count_7d", 0)) >= 1
    assert int(metrics.get("rejected_count_7d", 0)) >= 1
    assert int(metrics.get("invalid_count_7d", 0)) >= 1
    assert int(metrics.get("conflict_mark_count_7d", 0)) >= 1
    assert int(metrics.get("duplicate_combined_groups", 0)) >= 1

    lifecycle = body.get("lifecycle", {})
    assert int(lifecycle.get("window_days", 0)) == 7
    status_counts = lifecycle.get("candidate_status_counts", {})
    assert int(status_counts.get("ADOPTED", 0)) >= 1
    assert int(status_counts.get("REJECTED", 0)) >= 1
    assert int(status_counts.get("PENDING", 0)) >= 1
    assert float(lifecycle.get("adoption_rate", 0.0)) >= 0.0
    invalid_reasons = lifecycle.get("invalid_reason_counts", {})
    assert int(invalid_reasons.get("INVALID_CHUNK_A", 0)) >= 1
    transitions = lifecycle.get("recent_transitions", [])
    assert isinstance(transitions, list)
    assert any(str(item.get("event_type", "")) == "ADOPT" for item in transitions)


def test_mind_bitmap_candidate_timeline_endpoint_returns_candidate_events(tmp_path):
    client, db_url = _build_client(tmp_path)
    _seed_bitmap_tables(db_url)

    response = client.get("/mind/bitmap/candidates/cand_1/timeline?days=30&limit=20")
    assert response.status_code == 200
    body = response.json()
    assert body.get("status") == "ok"
    candidate = body.get("candidate", {})
    assert candidate.get("id") == "cand_1"
    assert candidate.get("episode_id") == "ep_1"
    events = body.get("events", [])
    assert isinstance(events, list)
    assert any(str(item.get("event_type", "")).upper() == "REJECT" for item in events)
    assert all(str(item.get("candidate_id", "")) == "cand_1" for item in events)


def test_mind_bitmap_candidate_timeline_filters_cross_episode_candidate_events(tmp_path):
    client, db_url = _build_client(tmp_path)
    _seed_bitmap_tables_with_episode_events(db_url)

    response = client.get("/mind/bitmap/candidates/cand_1/timeline?days=30&limit=20")
    assert response.status_code == 200
    body = response.json()
    events = body.get("events", [])

    assert any(str(item.get("summary", "")).find("manual_reject_ui") >= 0 for item in events)
    assert all(str(item.get("summary", "")).find("wrong_episode") < 0 for item in events)
    assert all(str(item.get("episode_id", "")) == "ep_1" for item in events)


def test_mind_bitmap_audit_endpoint_returns_transition_and_failure_summary(tmp_path):
    client, db_url = _build_client(tmp_path)
    _seed_bitmap_tables(db_url)

    response = client.get("/mind/bitmap/audit?days=30&limit=20&reason_limit=8")
    assert response.status_code == 200
    body = response.json()
    assert body.get("status") == "ok"
    totals = body.get("totals", {})
    assert int(totals.get("candidate_total", 0)) >= 1
    assert int((totals.get("status_counts", {}) or {}).get("REJECTED", 0)) >= 1
    transitions = body.get("candidate_transitions", [])
    assert any(str(row.get("candidate_id", "")) == "cand_1" for row in transitions)
    reasons = body.get("top_failure_reasons", [])
    reason_names = {str(row.get("reason", "")) for row in reasons}
    assert "INVALID_CHUNK_A" in reason_names
