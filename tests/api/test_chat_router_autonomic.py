import json
import re
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import chat_router
from core.memory.schema import MindItem, UserRule, WorkPackage, create_session_factory
from sophia_kernel.modules.mind_diary import ingest_trigger_event


def _client(tmp_path) -> TestClient:
    db_url = f"sqlite:///{tmp_path / 'chat_autonomic.db'}"
    chat_router.session_factory = create_session_factory(db_url)
    chat_router._legacy_backfilled = True
    app = FastAPI()
    app.include_router(chat_router.router)
    return TestClient(app)


def test_add_message_answer_contract(monkeypatch, tmp_path):
    client = _client(tmp_path)

    def _stub_llm(_text: str, _context: dict) -> str:
        return json.dumps(
            {
                "schema": "chat_contract.v0.1",
                "kind": "ANSWER",
                "text": "요청하신 범위는 auth 모듈입니다.",
                "needs": None,
                "task_plan": None,
                "sources": [{"type": "recent", "ref": "msg:latest"}],
                "confidence_model": 0.86,
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(chat_router, "_call_local_llm_contract", _stub_llm)

    res = client.post(
        "/chat/messages",
        json={
            "role": "user",
            "content": "현재 적용 범위 알려줘",
            "context_tag": "chat",
            "importance": 0.5,
            "status": "normal",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["messages"]) == 2
    assert body["messages"][1]["role"] == "sophia"
    assert body["messages"][1]["meta"]["kind"] == "ANSWER"


def test_add_message_task_plan_creates_work_package(monkeypatch, tmp_path):
    client = _client(tmp_path)

    def _stub_llm(_text: str, _context: dict) -> str:
        return json.dumps(
            {
                "schema": "chat_contract.v0.1",
                "kind": "TASK_PLAN",
                "text": "작업 계획을 등록했습니다.",
                "needs": None,
                "task_plan": {
                    "steps": [
                        {"title": "요구사항 정리", "executor": "local", "inputs": {}},
                        {"title": "코드 패치", "executor": "ide", "inputs": {"module": "chat"}},
                    ]
                },
                "sources": [{"type": "mind", "ref": "mind:task"}],
                "confidence_model": 0.73,
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(chat_router, "_call_local_llm_contract", _stub_llm)

    res = client.post(
        "/chat/messages",
        json={
            "role": "user",
            "content": "작업 계획 세워줘",
            "context_tag": "work",
            "importance": 0.5,
            "status": "normal",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["task_plan_work_id"]

    session = chat_router.session_factory()
    try:
        row = session.query(WorkPackage).filter(WorkPackage.id == body["task_plan_work_id"]).one_or_none()
        assert row is not None
        assert row.status == "READY"
    finally:
        session.close()


def test_clarify_response_learns_user_rule(monkeypatch, tmp_path):
    client = _client(tmp_path)

    def _invalid_json(_text: str, _context: dict) -> str:
        return "NOT_JSON"

    monkeypatch.setattr(chat_router, "_call_local_llm_contract", _invalid_json)

    first = client.post(
        "/chat/messages",
        json={
            "role": "user",
            "content": "이게 무슨 뜻이야",
            "context_tag": "chat",
            "importance": 0.5,
            "status": "normal",
        },
    )
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["messages"][1]["meta"]["kind"] == "CLARIFY"
    assert first_body["messages"][1]["status"] == "pending"

    second = client.post(
        "/chat/messages",
        json={
            "role": "user",
            "content": "여기서 범위는 auth 로그인 화면만 의미해",
            "context_tag": "chat",
            "importance": 0.5,
            "status": "normal",
        },
    )
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["learned_rule"] is not None

    session = chat_router.session_factory()
    try:
        rules = session.query(UserRule).all()
        assert len(rules) >= 1
        assert any(rule.type in {"term_meaning", "default_scope", "preference", "routing"} for rule in rules)
        term_items = session.query(MindItem).filter(MindItem.id.like("term:%")).all()
        assert len(term_items) >= 1
    finally:
        session.close()


def test_add_message_rejects_fixed_english_phrase_with_korean_fallback(monkeypatch, tmp_path):
    client = _client(tmp_path)

    def _stub_llm(_text: str, _context: dict) -> str:
        return json.dumps(
            {
                "schema": "chat_contract.v0.1",
                "kind": "ANSWER",
                "text": "I am maintaining the current context.",
                "needs": None,
                "task_plan": None,
                "sources": [{"type": "recent", "ref": "msg:latest"}],
                "confidence_model": 0.7,
            }
        )

    monkeypatch.setattr(chat_router, "_call_local_llm_contract", _stub_llm)

    res = client.post(
        "/chat/messages",
        json={
            "role": "user",
            "content": "이 기능의 적용 범위를 자세히 설명해줘",
            "context_tag": "chat",
            "importance": 0.5,
            "status": "normal",
        },
    )
    assert res.status_code == 200
    body = res.json()
    reply = body["messages"][1]
    content = reply["content"]
    meta = reply.get("meta") or {}
    assert "maintaining the current context" not in content.lower()
    assert "주인님" in content
    assert re.search(r"[가-힣]", content)
    assert bool(meta.get("fallback_applied", False)) is True


def test_add_message_unconscious_ping_hit_records_pattern(monkeypatch, tmp_path):
    client = _client(tmp_path)

    def _should_not_call(_text: str, _context: dict) -> str:
        raise AssertionError("llm must not be called on unconscious hit")

    monkeypatch.setattr(chat_router, "_call_local_llm_contract", _should_not_call)

    res = client.post(
        "/chat/messages",
        json={
            "role": "user",
            "content": "ping",
            "context_tag": "chat",
            "importance": 0.5,
            "status": "normal",
        },
    )
    assert res.status_code == 200
    body = res.json()
    reply = body["messages"][1]
    meta = reply.get("meta") or {}
    unconscious = meta.get("unconscious") or {}
    assert unconscious.get("pattern_id") == "PING_OK"
    assert unconscious.get("persona_level") == 0
    assert body["memory_used"] is False

    session = chat_router.session_factory()
    try:
        hit_item = (
            session.query(MindItem)
            .filter(MindItem.id == "unconscious:hit:ping_ok")
            .one_or_none()
        )
        assert hit_item is not None
    finally:
        session.close()


def test_add_message_unconscious_work_status_query(monkeypatch, tmp_path):
    client = _client(tmp_path)

    session = chat_router.session_factory()
    try:
        now = datetime.now(UTC)
        session.add(
            WorkPackage(
                id=f"wp_{uuid4().hex}",
                title="채팅 라우터 점검",
                description="",
                payload={},
                context_tag="work",
                status="READY",
                linked_node=None,
                created_at=now,
                acknowledged_at=None,
                completed_at=None,
                updated_at=now,
            )
        )
        session.add(
            WorkPackage(
                id=f"wp_{uuid4().hex}",
                title="마인드 이벤트 검증",
                description="",
                payload={},
                context_tag="work",
                status="IN_PROGRESS",
                linked_node=None,
                created_at=now,
                acknowledged_at=now,
                completed_at=None,
                updated_at=now,
            )
        )
        session.commit()
    finally:
        session.close()

    def _should_not_call(_text: str, _context: dict) -> str:
        raise AssertionError("llm must not be called on unconscious hit")

    monkeypatch.setattr(chat_router, "_call_local_llm_contract", _should_not_call)

    res = client.post(
        "/chat/messages",
        json={
            "role": "user",
            "content": "지금 무슨 작업 있니",
            "context_tag": "chat",
            "importance": 0.5,
            "status": "normal",
        },
    )
    assert res.status_code == 200
    body = res.json()
    reply = body["messages"][1]
    meta = reply.get("meta") or {}
    unconscious = meta.get("unconscious") or {}
    assert unconscious.get("pattern_id") == "WORK_STATUS_QUERY"
    assert "대기열 1건" in reply["content"]
    assert "진행 중 1건" in reply["content"]
    assert "노트 상태" in reply["content"]


def test_add_message_user_preference_creates_mind_item(monkeypatch, tmp_path):
    client = _client(tmp_path)

    def _stub_llm(_text: str, _context: dict) -> str:
        return json.dumps(
            {
                "schema": "chat_contract.v0.1",
                "kind": "ANSWER",
                "text": "요청을 반영하겠습니다.",
                "needs": None,
                "task_plan": None,
                "sources": [{"type": "recent", "ref": "msg:latest"}],
                "confidence_model": 0.8,
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(chat_router, "_call_local_llm_contract", _stub_llm)

    res = client.post(
        "/chat/messages",
        json={
            "role": "user",
            "content": "난 이 말투가 좋아",
            "context_tag": "chat",
            "importance": 0.5,
            "status": "normal",
        },
    )
    assert res.status_code == 200

    session = chat_router.session_factory()
    try:
        pref = session.query(MindItem).filter(MindItem.id == "preference:response_tone").one_or_none()
        assert pref is not None
        assert pref.type == "FOCUS"
    finally:
        session.close()


def test_add_message_repeated_topic_creates_mind_item(monkeypatch, tmp_path):
    client = _client(tmp_path)

    def _stub_llm(_text: str, _context: dict) -> str:
        return json.dumps(
            {
                "schema": "chat_contract.v0.1",
                "kind": "ANSWER",
                "text": "확인했습니다.",
                "needs": None,
                "task_plan": None,
                "sources": [{"type": "recent", "ref": "msg:latest"}],
                "confidence_model": 0.8,
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(chat_router, "_call_local_llm_contract", _stub_llm)

    for _ in range(3):
        res = client.post(
            "/chat/messages",
            json={
                "role": "user",
                "content": "topicalpha99 점검해줘",
                "context_tag": "chat",
                "importance": 0.5,
                "status": "normal",
            },
        )
        assert res.status_code == 200

    session = chat_router.session_factory()
    try:
        topic = session.query(MindItem).filter(MindItem.id == "topic:topicalpha99").one_or_none()
        assert topic is not None
        assert topic.type == "FOCUS"
    finally:
        session.close()


def test_chat_reply_uses_term_mapping_memory(monkeypatch, tmp_path):
    client = _client(tmp_path)

    session = chat_router.session_factory()
    try:
        ingest_trigger_event(
            session,
            event_type="TERM_MAPPING",
            payload={"term": "LANG-E1", "meaning": "논리 정제 1단계", "confidence": 0.9},
        )
        session.commit()
    finally:
        session.close()

    def _stub_llm(_text: str, _context: dict) -> str:
        return json.dumps(
            {
                "schema": "chat_contract.v0.1",
                "kind": "ANSWER",
                "text": "우선순위를 확인해 보겠습니다. 이어서 진행 단계를 정리하겠습니다.",
                "needs": None,
                "task_plan": None,
                "sources": [{"type": "recent", "ref": "msg:latest"}],
                "confidence_model": 0.81,
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(chat_router, "_call_local_llm_contract", _stub_llm)

    res = client.post(
        "/chat/messages",
        json={
            "role": "user",
            "content": "LANG-E1 먼저 해야해?",
            "context_tag": "chat",
            "importance": 0.5,
            "status": "normal",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["memory_used"] is True
    assert "term:lang-e1" in body["memory_hits"]
    reply = body["messages"][1]
    assert reply["meta"]["memory_used"] is True
    assert "lang-e1" in reply["content"].lower() or "논리 정제" in reply["content"]


def test_chat_reply_applies_preference_tone_memory(monkeypatch, tmp_path):
    client = _client(tmp_path)

    def _stub_llm(_text: str, _context: dict) -> str:
        return json.dumps(
            {
                "schema": "chat_contract.v0.1",
                "kind": "ANSWER",
                "text": "요청하신 작업을 단계적으로 설명하겠습니다. 먼저 범위를 정리하고 다음 단계를 제안하겠습니다.",
                "needs": None,
                "task_plan": None,
                "sources": [{"type": "recent", "ref": "msg:latest"}],
                "confidence_model": 0.8,
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(chat_router, "_call_local_llm_contract", _stub_llm)

    first = client.post(
        "/chat/messages",
        json={
            "role": "user",
            "content": "오늘 할 일 알려줘",
            "context_tag": "chat",
            "importance": 0.5,
            "status": "normal",
        },
    )
    assert first.status_code == 200
    first_reply = first.json()["messages"][1]["content"]

    session = chat_router.session_factory()
    try:
        ingest_trigger_event(
            session,
            event_type="USER_PREFERENCE",
            payload={"key": "response_tone", "value": "짧게 답해줘", "confidence": 0.8},
        )
        session.commit()
    finally:
        session.close()

    second = client.post(
        "/chat/messages",
        json={
            "role": "user",
            "content": "오늘 할 일 알려줘",
            "context_tag": "chat",
            "importance": 0.5,
            "status": "normal",
        },
    )
    assert second.status_code == 200
    second_body = second.json()
    second_reply = second_body["messages"][1]["content"]

    assert second_body["memory_used"] is True
    assert "preference:response_tone" in second_body["memory_hits"]
    assert second_reply != first_reply
    assert len(second_reply) < len(first_reply)


def test_chat_reply_uses_memory_when_llm_unavailable(monkeypatch, tmp_path):
    client = _client(tmp_path)

    session = chat_router.session_factory()
    try:
        ingest_trigger_event(
            session,
            event_type="TERM_MAPPING",
            payload={"term": "lang-e1", "meaning": "논리 정제 1단계", "confidence": 0.9},
        )
        session.commit()
    finally:
        session.close()

    def _down_llm(_text: str, _context: dict) -> str:
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(chat_router, "_call_local_llm_contract", _down_llm)

    res = client.post(
        "/chat/messages",
        json={
            "role": "user",
            "content": "lang-e1 먼저 확인할까?",
            "context_tag": "chat",
            "importance": 0.5,
            "status": "normal",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["memory_used"] is True
    assert "term:lang-e1" in body["memory_hits"]
    reply = body["messages"][1]
    assert reply["meta"]["fallback_applied"] is True
    assert "논리 정제" in reply["content"] or "lang-e1" in reply["content"].lower()
