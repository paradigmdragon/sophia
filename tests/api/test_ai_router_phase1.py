import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import ai_router, ledger_events
from core.ai.ai_router import AIRouterService
from core.ai.providers.base import ProviderResult
from core.forest import layout as forest_layout
from core.memory.schema import MindItem, create_session_factory


def _client(tmp_path, monkeypatch) -> tuple[TestClient, Path, list[dict]]:
    db_url = f"sqlite:///{tmp_path / 'ai_router.db'}"
    session_factory = create_session_factory(db_url)
    ai_router._SessionLocal = session_factory
    ai_router._ai_service = AIRouterService(provider_default="rule", mode="single")

    forest_root = tmp_path / "forest" / "project"
    monkeypatch.setattr(forest_layout, "FOREST_ROOT", forest_root)
    audit_records: list[dict] = []
    if ledger_events.audit_ledger is not None:
        monkeypatch.setattr(
            ledger_events.audit_ledger,
            "append_audit_record",
            lambda record: audit_records.append(record),
        )

    app = FastAPI()
    app.include_router(ai_router.router)
    return TestClient(app), forest_root, audit_records


def _ledger_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        out.append(json.loads(text))
    return out


def test_ai_ingest_stores_mind_candidate_and_redacts_ledger(tmp_path, monkeypatch):
    client, forest_root, audit_records = _client(tmp_path, monkeypatch)
    raw = "사용자 메모 SOPHIA_SECRET_SENTINEL_9f3a2 TOKEN=abcd1234 와 우선순위 정리"

    res = client.post(
        "/ai/ingest",
        json={
            "text": raw,
            "source": "shortcut.share",
            "provider": "rule",
            "mode": "single",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["contract"]["schema"] == "ingest_contract.v0.1"
    assert body["mind_item"]["type"] == "FOCUS"
    assert body["meta"]["provider_final"] == "rule"
    assert body["meta"]["quality_state"] == "SANITIZED"
    assert isinstance(body["meta"]["redacted_fields"], list)
    assert body["meta"]["redacted_fields"]

    session = ai_router._SessionLocal()
    try:
        row = session.query(MindItem).filter(MindItem.id == body["mind_item"]["id"]).one_or_none()
        assert row is not None
        assert "SOPHIA_SECRET_SENTINEL_9f3a2" not in (row.summary_120 or "")
        assert "quality:sanitized" in (row.tags or [])
    finally:
        session.close()

    ledger_path = forest_root / "sophia" / "ledger" / "ledger.jsonl"
    rows = _ledger_rows(ledger_path)
    assert any(item.get("event_type") == "AI_INGEST_PROCESSED" for item in rows)
    joined = json.dumps(rows, ensure_ascii=False)
    assert "TOKEN=abcd1234" not in joined
    assert "SOPHIA_SECRET_SENTINEL_9f3a2" not in joined

    last = next(item for item in reversed(rows) if item.get("event_type") == "AI_INGEST_PROCESSED")
    payload = last["payload"]
    for key in [
        "input_hash",
        "input_len",
        "task",
        "endpoint",
        "provider_final",
        "fallback_applied",
        "gate_reason",
        "mind_item_id",
        "attempts_count",
        "quality_state",
    ]:
        assert key in payload

    assert audit_records, "expected captured audit records"
    ai_audit = [item for item in audit_records if str(item.get("skill_id", "")).startswith("ai.")]
    assert ai_audit
    record = ai_audit[-1]
    assert "meta" in record
    for key in ["task", "provider_final", "fallback_applied", "gate_reason", "endpoint"]:
        assert key in record["meta"]


def test_ai_transcript_rules_diff_store_candidates(tmp_path, monkeypatch):
    client, forest_root, _ = _client(tmp_path, monkeypatch)

    transcript = client.post(
        "/ai/transcript/process",
        json={"text": "회의 내용 정리, 다음 액션은 테스트 점검", "provider": "rule", "mode": "single"},
    )
    assert transcript.status_code == 200
    assert transcript.json()["contract"]["schema"] == "transcript_contract.v0.1"
    assert transcript.json()["mind_item"]["type"] == "TASK"

    rules = client.post(
        "/ai/rules/candidates",
        json={
            "text_bundle": ["항상 테스트 먼저", "로그는 짧게"],
            "refs": ["msg_1", "msg_2"],
            "provider": "rule",
            "mode": "single",
        },
    )
    assert rules.status_code == 200
    assert rules.json()["contract"]["schema"] == "rule_candidate.v0.1"
    assert rules.json()["mind_item"]["type"] == "FOCUS"

    diff = client.post(
        "/ai/diff/summarize",
        json={
            "before_text": "A는 기본 정책",
            "after_text": "A는 변경 정책",
            "doc_path": "docs/spec.md",
            "provider": "rule",
            "mode": "single",
        },
    )
    assert diff.status_code == 200
    assert diff.json()["contract"]["schema"] == "diff_contract.v0.1"
    assert diff.json()["mind_item"]["type"] == "ALERT"

    ledger_path = forest_root / "sophia" / "ledger" / "ledger.jsonl"
    rows = _ledger_rows(ledger_path)
    event_types = [item.get("event_type") for item in rows]
    assert "AI_TRANSCRIPT_PROCESSED" in event_types
    assert "AI_RULE_CANDIDATES_PROCESSED" in event_types
    assert "AI_DIFF_SUMMARIZED" in event_types


def test_ai_fallback_marks_quality_and_attempts(tmp_path, monkeypatch):
    client, _, _ = _client(tmp_path, monkeypatch)

    original = ai_router._ai_service.providers["ollama"]

    class _FailingOllama:
        name = "ollama"

        def run(self, task, payload):
            _ = task
            _ = payload
            return ProviderResult(provider="ollama", ok=False, available=True, error="timeout_simulated")

    ai_router._ai_service.providers["ollama"] = _FailingOllama()
    try:
        res = client.post(
            "/ai/ingest",
            json={
                "text": "fallback 검증",
                "source": "fallback-test",
                "provider": "ollama",
                "mode": "fallback",
            },
        )
    finally:
        ai_router._ai_service.providers["ollama"] = original

    assert res.status_code == 200
    body = res.json()
    assert body["meta"]["provider_final"] == "rule"
    assert body["meta"]["fallback_applied"] is True
    assert int(body["meta"]["attempts_count"]) >= 2
    assert body["meta"]["quality_state"] == "FALLBACK"


def test_ai_empty_input_returns_400_with_code(tmp_path, monkeypatch):
    client, _, _ = _client(tmp_path, monkeypatch)
    res = client.post(
        "/ai/ingest",
        json={
            "text": "",
            "source": "empty-test",
            "provider": "rule",
            "mode": "single",
        },
    )
    assert res.status_code == 400
    body = res.json()
    assert body["detail"]["code"] == "AI_EMPTY_INPUT"
