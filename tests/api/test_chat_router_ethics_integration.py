import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import chat_router
from core.ethics.gate import CommitMeta, EthicsOutcome, GateOutput
from core.memory.schema import create_session_factory


def _client(tmp_path) -> TestClient:
    db_url = f"sqlite:///{tmp_path / 'chat_ethics.db'}"
    chat_router.session_factory = create_session_factory(db_url)
    chat_router._legacy_backfilled = True
    app = FastAPI()
    app.include_router(chat_router.router)
    return TestClient(app)


def _fixed_commit_gate() -> GateOutput:
    return GateOutput(
        outcome=EthicsOutcome.FIX,
        reason_codes=[],
        commit_meta=CommitMeta(
            event_id="cmt_test",
            timestamp="2026-02-15T00:00:00Z",
            subject="reply",
            source="assistant",
            facet="CANDIDATE",
            refs=["chat"],
            hash="sha256:test",
            policy_version="ethics_protocol_v1_0",
            redaction={"pii_removed": False, "fields": []},
            review={"required": True, "state": "pending"},
        ),
    )


def test_chat_messages_calls_pre_output_and_pre_commit_gates(monkeypatch, tmp_path):
    client = _client(tmp_path)

    counters = {"output": 0, "commit": 0, "events": []}

    def _stub_llm(_text: str, _context: dict) -> str:
        return json.dumps(
            {
                "schema": "chat_contract.v0.1",
                "kind": "ANSWER",
                "text": "정상 응답입니다.",
                "needs": None,
                "task_plan": None,
                "sources": [{"type": "recent", "ref": "msg:latest"}],
                "confidence_model": 0.9,
            }
        )

    def _stub_pre_output(_gate_input):
        counters["output"] += 1
        return GateOutput(outcome=EthicsOutcome.ALLOW, reason_codes=[])

    def _stub_pre_commit(_gate_input):
        counters["commit"] += 1
        return _fixed_commit_gate()

    def _stub_lifecycle(event_type: str, payload: dict, skill_id: str = "chat.lifecycle"):
        counters["events"].append((event_type, skill_id, payload.get("endpoint", "")))
        return True

    monkeypatch.setattr(chat_router, "_call_local_llm_contract", _stub_llm)
    monkeypatch.setattr(chat_router, "pre_output_gate", _stub_pre_output)
    monkeypatch.setattr(chat_router, "pre_commit_gate", _stub_pre_commit)
    monkeypatch.setattr(chat_router, "write_lifecycle_event", _stub_lifecycle)

    res = client.post(
        "/chat/messages",
        json={
            "role": "user",
            "content": "질문입니다",
            "context_tag": "chat",
            "importance": 0.5,
            "status": "normal",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["messages"]) == 2
    assert counters["output"] == 1
    assert counters["commit"] == 1
    assert any(item[0] == "ETHICS_FIX_COMMITTED" for item in counters["events"])


def test_chat_message_calls_pre_output_and_pre_commit_gates(monkeypatch, tmp_path):
    client = _client(tmp_path)

    counters = {"output": 0, "commit": 0}

    def _stub_pre_output(_gate_input):
        counters["output"] += 1
        return GateOutput(outcome=EthicsOutcome.ALLOW, reason_codes=[])

    def _stub_pre_commit(_gate_input):
        counters["commit"] += 1
        return _fixed_commit_gate()

    monkeypatch.setattr(chat_router, "pre_output_gate", _stub_pre_output)
    monkeypatch.setattr(chat_router, "pre_commit_gate", _stub_pre_commit)

    res = client.post(
        "/chat/message",
        json={
            "content": "안녕하세요",
            "context_tag": "chat",
            "channel": "General",
        },
    )
    assert res.status_code == 200
    assert counters["output"] == 1
    assert counters["commit"] == 1
