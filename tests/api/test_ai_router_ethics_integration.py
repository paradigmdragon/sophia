from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import ai_router
from core.ai.ai_router import AIRouterService
from core.ethics.gate import CommitMeta, EthicsOutcome, GateOutput
from core.memory.schema import create_session_factory


def _client(tmp_path) -> TestClient:
    db_url = f"sqlite:///{tmp_path / 'ai_ethics.db'}"
    session_factory = create_session_factory(db_url)
    ai_router._SessionLocal = session_factory
    ai_router._ai_service = AIRouterService(provider_default="rule", mode="single")

    app = FastAPI()
    app.include_router(ai_router.router)
    return TestClient(app)


def _fixed_commit_gate() -> GateOutput:
    return GateOutput(
        outcome=EthicsOutcome.FIX,
        reason_codes=[],
        commit_meta=CommitMeta(
            event_id="cmt_ai",
            timestamp="2026-02-15T00:00:00Z",
            subject="summary",
            source="system",
            facet="CANDIDATE",
            refs=["ai"],
            hash="sha256:test",
            policy_version="ethics_protocol_v1_0",
            redaction={"pii_removed": False, "fields": []},
            review={"required": True, "state": "pending"},
        ),
    )


def test_ai_router_calls_pre_output_and_pre_commit(monkeypatch, tmp_path):
    client = _client(tmp_path)
    counters = {"output": 0, "commit": 0, "events": []}

    def _stub_pre_output(_gate_input):
        counters["output"] += 1
        return GateOutput(outcome=EthicsOutcome.ALLOW, reason_codes=[])

    def _stub_pre_commit(_gate_input):
        counters["commit"] += 1
        return _fixed_commit_gate()

    def _stub_lifecycle(event_type: str, payload: dict, skill_id: str = "chat.lifecycle"):
        counters["events"].append((event_type, skill_id, payload.get("endpoint", "")))
        return True

    monkeypatch.setattr(ai_router, "pre_output_gate", _stub_pre_output)
    monkeypatch.setattr(ai_router, "pre_commit_gate", _stub_pre_commit)
    monkeypatch.setattr(ai_router, "write_lifecycle_event", _stub_lifecycle)

    res = client.post(
        "/ai/ingest",
        json={
            "text": "윤리 게이트 통합 테스트",
            "source": "manual",
            "provider": "rule",
            "mode": "single",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["meta"]["ethics"]["outcome"] == "ALLOW"
    assert counters["output"] == 1
    assert counters["commit"] == 1
    assert any(item[0] == "ETHICS_FIX_COMMITTED" for item in counters["events"])


def test_ai_router_pending_output_sets_required_inputs(monkeypatch, tmp_path):
    client = _client(tmp_path)

    def _stub_pre_output(_gate_input):
        return GateOutput(
            outcome=EthicsOutcome.PENDING,
            reason_codes=["INSUFFICIENT_EVIDENCE"],
            required_inputs=["verified_source"],
            next_action={"type": "verify_route", "payload": {"hint": "근거 확인"}},
        )

    def _stub_pre_commit(_gate_input):
        return _fixed_commit_gate()

    monkeypatch.setattr(ai_router, "pre_output_gate", _stub_pre_output)
    monkeypatch.setattr(ai_router, "pre_commit_gate", _stub_pre_commit)

    res = client.post(
        "/ai/ingest",
        json={
            "text": "불확실 출력 제어",
            "source": "manual",
            "provider": "rule",
            "mode": "single",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["meta"]["ethics"]["outcome"] == "PENDING"
    assert body["meta"]["ethics"]["required_inputs"] == ["verified_source"]
    assert body["contract"]["summary_120"].startswith("확인 불가")
