from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import chat_router, work_router
from core.ethics.gate import CommitMeta, EthicsOutcome, GateOutput
from core.forest import layout as forest_layout
from core.memory.schema import create_session_factory


def _client(tmp_path, monkeypatch) -> TestClient:
    db_url = f"sqlite:///{tmp_path / 'work_ethics.db'}"
    session_factory = create_session_factory(db_url)
    chat_router.session_factory = session_factory
    chat_router._legacy_backfilled = True
    work_router.session_factory = session_factory

    forest_root = tmp_path / "forest" / "project"
    monkeypatch.setattr(forest_layout, "FOREST_ROOT", forest_root)

    app = FastAPI()
    app.include_router(chat_router.router)
    app.include_router(work_router.router)
    return TestClient(app)


def _fixed_commit_gate() -> GateOutput:
    return GateOutput(
        outcome=EthicsOutcome.FIX,
        reason_codes=[],
        commit_meta=CommitMeta(
            event_id="cmt_work",
            timestamp="2026-02-15T00:00:00Z",
            subject="action",
            source="system",
            facet="CANDIDATE",
            refs=["work"],
            hash="sha256:test",
            policy_version="ethics_protocol_v1_0",
            redaction={"pii_removed": False, "fields": []},
            review={"required": True, "state": "pending"},
        ),
    )


def test_work_router_calls_pre_output_and_pre_commit(monkeypatch, tmp_path):
    client = _client(tmp_path, monkeypatch)

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

    monkeypatch.setattr(work_router, "pre_output_gate", _stub_pre_output)
    monkeypatch.setattr(work_router, "pre_commit_gate", _stub_pre_commit)
    monkeypatch.setattr(work_router, "write_lifecycle_event", _stub_lifecycle)

    create = client.post(
        "/work/packages",
        json={
            "kind": "IMPLEMENT",
            "context_tag": "work",
            "linked_node": "forest:test",
            "acceptance_criteria": ["pytest pass"],
            "deliverables": ["return_payload.json"],
            "title": "Ethics Test Package",
            "description": "ethics integration",
        },
    )
    assert create.status_code == 200
    package_id = create.json()["package"]["id"]

    report = client.post(
        f"/work/packages/{package_id}/report",
        json={
            "work_package_id": package_id,
            "status": "DONE",
            "signals": [],
            "artifacts": ["logs/report.txt"],
            "notes": "completed",
        },
    )
    assert report.status_code == 200

    assert counters["output"] >= 2
    assert counters["commit"] >= 2
    assert any(item[0] == "ETHICS_FIX_COMMITTED" for item in counters["events"])
