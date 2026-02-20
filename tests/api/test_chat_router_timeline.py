from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import chat_router
from core.engine.schema import Base as EngineBase
from core.engine.schema import Backbone, Candidate, Episode, Event
from core.memory.schema import create_session_factory


def _client(tmp_path) -> TestClient:
    db_url = f"sqlite:///{tmp_path / 'chat_timeline.db'}"
    chat_router.session_factory = create_session_factory(db_url)
    chat_router._legacy_backfilled = True
    app = FastAPI()
    app.include_router(chat_router.router)
    return TestClient(app)


def test_send_message_writes_single_timeline_with_context_tag(tmp_path):
    client = _client(tmp_path)

    res = client.post(
        "/chat/message",
        json={
            "content": "이건 work-task로 등록해줘",
            "context_tag": "work-task",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["context_tag"] == "work"
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][0]["context_tag"] == "work"
    assert body["messages"][1]["role"] == "sophia"
    assert body["messages"][1]["context_tag"] == "work"

    history = client.get("/chat/history").json()
    assert len(history) == 2
    assert all("context_tag" in item for item in history)


def test_history_filter_by_context_tag(tmp_path):
    client = _client(tmp_path)

    client.post("/chat/message", json={"content": "일반 대화", "context_tag": "general"})
    client.post("/chat/message", json={"content": "숲 분석", "context_tag": "forest:alpha"})

    all_rows = client.get("/chat/history").json()
    forest_rows = client.get("/chat/history", params={"context_tag": "forest:*"}).json()

    assert len(all_rows) == 4
    assert len(forest_rows) == 2
    assert all(row["context_tag"].startswith("forest:") for row in forest_rows)


def test_question_pool_three_hits_creates_pending_message(tmp_path):
    client = _client(tmp_path)

    for _ in range(3):
        res = client.post(
            "/chat/questions/signal",
            json={
                "cluster_id": "scope_ambiguity",
                "description": "범위 불명확",
                "risk_score": 0.64,
                "linked_node": "module_auth",
            },
        )
        assert res.status_code == 200

    pool_rows = client.get("/chat/questions/pool").json()
    target = next(row for row in pool_rows if row["cluster_id"] == "scope_ambiguity")
    assert target["hit_count"] == 3
    assert target["status"] == "pending"
    assert target["asked_count"] == 1
    assert len(target["evidence"]) == 3

    pending_rows = client.get("/chat/pending").json()
    assert len(pending_rows) == 1
    assert pending_rows[0]["role"] == "sophia"
    assert pending_rows[0]["context_tag"] == "question-queue"
    assert pending_rows[0]["status"] == "pending"
    assert pending_rows[0]["linked_cluster"] == "scope_ambiguity"


def test_question_dedup_ack_resolve_and_read(tmp_path):
    client = _client(tmp_path)

    for _ in range(3):
        client.post(
            "/chat/questions/signal",
            json={
                "cluster_id": "dependency_missing",
                "description": "의존 관계 불명확",
                "risk_score": 0.72,
                "snippet": "의존 모듈 누락",
                "source": "spec_v2.md",
            },
        )

    first_pending = client.get("/chat/pending").json()
    assert len(first_pending) == 1
    msg_id = first_pending[0]["id"]

    # Duplicate signal should not create another pending message.
    client.post(
        "/chat/questions/signal",
        json={
            "cluster_id": "dependency_missing",
            "description": "의존 관계 불명확",
            "risk_score": 0.72,
            "snippet": "의존 모듈 누락",
            "source": "spec_v2.md",
        },
    )
    second_pending = client.get("/chat/pending").json()
    assert len(second_pending) == 1

    ack_res = client.post("/chat/questions/dependency_missing/ack")
    assert ack_res.status_code == 200
    assert ack_res.json()["question_status"] == "acknowledged"

    read_res = client.post(f"/chat/messages/{msg_id}/read")
    assert read_res.status_code == 200
    assert read_res.json()["message"]["status"] in {"read", "acknowledged"}

    resolve_res = client.post("/chat/questions/dependency_missing/resolve")
    assert resolve_res.status_code == 200
    assert resolve_res.json()["question_status"] == "resolved"

    pool_rows = client.get("/chat/questions/pool").json()
    target = next(row for row in pool_rows if row["cluster_id"] == "dependency_missing")
    assert target["status"] == "resolved"


def test_question_response_message_triggers_reanalysis(tmp_path):
    client = _client(tmp_path)

    signal_res = client.post(
        "/chat/questions/signal",
        json={
            "cluster_id": "scope_ambiguity",
            "description": "범위 불명확",
            "risk_score": 0.6,
        },
    )
    assert signal_res.status_code == 200

    msg_res = client.post(
        "/chat/messages",
        json={
            "role": "user",
            "content": "적용 범위를 결정했습니다. 성공 조건도 명시했습니다.",
            "context_tag": "question-queue",
            "linked_cluster": "scope_ambiguity",
        },
    )
    assert msg_res.status_code == 200

    pool_rows = client.get("/chat/questions/pool").json()
    target = next(row for row in pool_rows if row["cluster_id"] == "scope_ambiguity")
    assert target["status"] == "resolved"


def test_add_message_user_chat_context_autoreplies(tmp_path):
    client = _client(tmp_path)
    res = client.post(
        "/chat/messages",
        json={
            "role": "user",
            "content": "대답해줘",
            "context_tag": "chat",
            "importance": 0.5,
            "status": "normal",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["context_tag"] == "chat"
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][1]["role"] == "sophia"


def test_add_message_user_system_context_forbidden(tmp_path):
    client = _client(tmp_path)
    res = client.post(
        "/chat/messages",
        json={
            "role": "user",
            "content": "내부 로그",
            "context_tag": "system",
            "importance": 0.5,
            "status": "normal",
        },
    )
    assert res.status_code == 400
    assert "reserved for internal events" in res.json()["detail"]


def test_add_message_defaults_to_chat_context(tmp_path):
    client = _client(tmp_path)
    res = client.post(
        "/chat/messages",
        json={
            "role": "user",
            "content": "기본 컨텍스트 테스트",
            "importance": 0.5,
            "status": "normal",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["context_tag"] == "chat"


def test_chat_state_bitmap_summary_includes_invalid_and_rejected_counters(tmp_path):
    client = _client(tmp_path)

    session = chat_router.session_factory()
    try:
        EngineBase.metadata.create_all(session.get_bind())
        now = datetime.now(UTC)
        session.add(Episode(episode_id="ep_bitmap_state", status="UNDECIDED", log_ref={"uri": "memory://state", "type": "test"}))
        session.add(
            Candidate(
                candidate_id="cand_rejected_state",
                episode_id="ep_bitmap_state",
                proposed_by="test",
                backbone_bits=0x0000,
                facets_json=[],
                confidence=10,
                status="REJECTED",
                proposed_at=now,
                note_thin="rejected sample",
            )
        )
        session.add(
            Event(
                event_id="evt_bitmap_invalid_state",
                episode_id="ep_bitmap_state",
                type="BITMAP_INVALID",
                payload={"stage": "propose", "reason": "INVALID_CHUNK_A", "bits_raw": 0xF000},
                at=now,
            )
        )
        session.add(
            Event(
                event_id="evt_conflict_mark_state",
                episode_id="ep_bitmap_state",
                type="CONFLICT_MARK",
                payload={"rule_id": "D_EQUIVALENCE_OPPOSITIONAL"},
                at=now,
            )
        )
        session.add_all(
            [
                Backbone(
                    backbone_id="bb_dup_1",
                    episode_id="ep_bitmap_state",
                    bits_a=1,
                    bits_b=1,
                    bits_c=1,
                    bits_d=1,
                    combined_bits=0x1111,
                    role="PRIMARY",
                    origin="ADOPT",
                    deprecated=False,
                    adopted_at=now,
                ),
                Backbone(
                    backbone_id="bb_dup_2",
                    episode_id="ep_bitmap_state",
                    bits_a=1,
                    bits_b=1,
                    bits_c=1,
                    bits_d=1,
                    combined_bits=0x1111,
                    role="ALTERNATIVE",
                    origin="ADOPT",
                    deprecated=False,
                    adopted_at=now,
                ),
            ]
        )
        session.commit()
    finally:
        session.close()

    res = client.get("/chat/state")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    bitmap = body.get("bitmap", {})
    metrics = bitmap.get("metrics", {})
    assert int(metrics.get("rejected_count_7d", 0)) >= 1
    assert int(metrics.get("invalid_count_7d", 0)) >= 1
    assert int(metrics.get("conflict_mark_count_7d", 0)) >= 1
    assert int(metrics.get("duplicate_combined_groups", 0)) >= 1
    assert int(metrics.get("duplicate_backbone_rows", 0)) >= 1
    assert isinstance(bitmap.get("invalid_recent", []), list)
