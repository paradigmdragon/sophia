from __future__ import annotations

import json
from pathlib import Path

import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import ai_router, ledger_events
from core.ai.ai_router import AIRouterService
from core.ai.providers.base import ProviderResult
from core.forest import layout as forest_layout
from core.memory.schema import create_session_factory


class _FakeResponse:
    def __init__(self, *, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def _client(tmp_path, monkeypatch) -> tuple[TestClient, Path, list[dict]]:
    db_url = f"sqlite:///{tmp_path / 'ai_foundation_bridge.db'}"
    session_factory = create_session_factory(db_url)
    ai_router._SessionLocal = session_factory
    ai_router._ai_service = AIRouterService(provider_default="rule", mode="fallback")

    class _FailingOllama:
        name = "ollama"

        def run(self, task, payload):
            _ = task
            _ = payload
            return ProviderResult(provider="ollama", ok=False, available=True, error="ollama_unavailable")

    ai_router._ai_service.providers["ollama"] = _FailingOllama()

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
        if not line.strip():
            continue
        out.append(json.loads(line))
    return out


def test_foundation_ingest_success_without_fallback(tmp_path, monkeypatch):
    client, forest_root, audit_records = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("AI_ALLOW_EXTERNAL", "false")
    monkeypatch.setenv("AI_FOUNDATION_BRIDGE_URL", "http://127.0.0.1:8765")

    monkeypatch.setattr(
        "core.ai.providers.foundation_provider.requests.get",
        lambda *args, **kwargs: _FakeResponse(
            status_code=200,
            payload={"status": "ok", "provider": "foundation", "available": True, "version": "0.1.0"},
        ),
    )
    monkeypatch.setattr(
        "core.ai.providers.foundation_provider.requests.post",
        lambda *args, **kwargs: _FakeResponse(
            status_code=200,
            payload={
                "ok": True,
                "contract": {
                    "schema": "ingest_contract.v0.1",
                    "summary_120": "bridge 요약",
                    "entities": [],
                    "tags": ["bridge", "foundation"],
                    "context_tag": "doc",
                    "confidence_model": 0.81,
                },
                "meta": {"provider": "foundation", "latency_ms": 142},
            },
        ),
    )

    res = client.post(
        "/ai/ingest",
        json={"text": "테스트 입력", "provider": "foundation", "mode": "fallback", "source": "poc"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["meta"]["provider_primary"] == "foundation"
    assert body["meta"]["provider_final"] == "foundation"
    assert body["meta"]["fallback_applied"] is False
    assert body["meta"]["quality_state"] == "NORMAL"
    assert body["mind_item"]["id"]

    ledger_path = forest_root / "sophia" / "ledger" / "ledger.jsonl"
    rows = _ledger_rows(ledger_path)
    assert rows
    payload = rows[-1]["payload"]
    assert payload["provider_final"] == "foundation"
    assert payload["fallback_applied"] is False

    assert audit_records
    last = audit_records[-1]
    assert last["meta"]["provider_final"] == "foundation"
    assert last["meta"]["fallback_applied"] is False


def test_foundation_ingest_falls_back_when_bridge_down(tmp_path, monkeypatch):
    client, _, _ = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("AI_ALLOW_EXTERNAL", "false")
    monkeypatch.setenv("AI_FOUNDATION_BRIDGE_URL", "http://127.0.0.1:8765")

    def _network_error(*args, **kwargs):
        raise requests.ConnectionError("bridge down")

    monkeypatch.setattr("core.ai.providers.foundation_provider.requests.get", _network_error)

    res = client.post(
        "/ai/ingest",
        json={"text": "짧음", "provider": "foundation", "mode": "fallback", "source": "poc"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["meta"]["provider_primary"] == "foundation"
    assert body["meta"]["provider_final"] == "rule"
    assert body["meta"]["fallback_applied"] is True
    assert body["meta"]["quality_state"] == "FALLBACK"
    attempts = body["meta"]["attempts"]
    foundation_attempt = next(item for item in attempts if item["provider"] == "foundation")
    assert foundation_attempt["error"] == "BRIDGE_NETWORK_ERROR"


def test_foundation_ingest_timeout_falls_back(tmp_path, monkeypatch):
    client, _, _ = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("AI_ALLOW_EXTERNAL", "false")
    monkeypatch.setenv("AI_FOUNDATION_BRIDGE_URL", "http://127.0.0.1:8765")

    monkeypatch.setattr(
        "core.ai.providers.foundation_provider.requests.get",
        lambda *args, **kwargs: _FakeResponse(
            status_code=200,
            payload={"status": "ok", "provider": "foundation", "available": True, "version": "0.1.0"},
        ),
    )

    def _timeout(*args, **kwargs):
        raise requests.Timeout("timeout")

    monkeypatch.setattr("core.ai.providers.foundation_provider.requests.post", _timeout)

    res = client.post(
        "/ai/ingest",
        json={"text": "짧음", "provider": "foundation", "mode": "fallback", "source": "poc"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["meta"]["provider_final"] == "rule"
    assert body["meta"]["fallback_applied"] is True
    assert body["meta"]["quality_state"] == "FALLBACK"
    attempts = body["meta"]["attempts"]
    foundation_attempt = next(item for item in attempts if item["provider"] == "foundation")
    assert foundation_attempt["error"] == "BRIDGE_TIMEOUT"
    assert int(body["meta"]["attempts_count"]) >= 2


def test_foundation_ingest_blocks_non_local_bridge_host(tmp_path, monkeypatch):
    client, _, _ = _client(tmp_path, monkeypatch)
    monkeypatch.setenv("AI_ALLOW_EXTERNAL", "false")
    monkeypatch.setenv("AI_FOUNDATION_BRIDGE_URL", "http://203.0.113.10:8765")

    calls = {"get": 0, "post": 0}

    def _count_get(*args, **kwargs):
        calls["get"] += 1
        return _FakeResponse(status_code=500, payload={"status": "error"})

    def _count_post(*args, **kwargs):
        calls["post"] += 1
        return _FakeResponse(status_code=500, payload={"ok": False})

    monkeypatch.setattr("core.ai.providers.foundation_provider.requests.get", _count_get)
    monkeypatch.setattr("core.ai.providers.foundation_provider.requests.post", _count_post)

    res = client.post(
        "/ai/ingest",
        json={"text": "짧음", "provider": "foundation", "mode": "fallback", "source": "poc"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["meta"]["provider_final"] == "rule"
    assert body["meta"]["fallback_applied"] is True
    assert body["meta"]["quality_state"] == "FALLBACK"
    attempts = body["meta"]["attempts"]
    foundation_attempt = next(item for item in attempts if item["provider"] == "foundation")
    assert foundation_attempt["error"] == "BRIDGE_HOST_BLOCKED"
    assert calls["get"] == 0
    assert calls["post"] == 0
