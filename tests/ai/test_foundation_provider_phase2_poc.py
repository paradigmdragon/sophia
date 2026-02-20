from __future__ import annotations

import requests

from core.ai.providers.foundation_provider import FoundationProvider


class _FakeResponse:
    def __init__(self, *, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_foundation_provider_host_blocked(monkeypatch):
    monkeypatch.setenv("AI_ALLOW_EXTERNAL", "false")
    monkeypatch.setenv("AI_FOUNDATION_BRIDGE_URL", "http://203.0.113.10:8765")

    calls = {"get": 0, "post": 0}
    monkeypatch.setattr(
        "core.ai.providers.foundation_provider.requests.get",
        lambda *args, **kwargs: calls.__setitem__("get", calls["get"] + 1),
    )
    monkeypatch.setattr(
        "core.ai.providers.foundation_provider.requests.post",
        lambda *args, **kwargs: calls.__setitem__("post", calls["post"] + 1),
    )

    provider = FoundationProvider()
    result = provider.run("ingest", {"text": "테스트"})
    assert result.ok is False
    assert result.error == "BRIDGE_HOST_BLOCKED"
    assert calls["get"] == 0
    assert calls["post"] == 0


def test_foundation_provider_bridge_unavailable(monkeypatch):
    monkeypatch.setenv("AI_ALLOW_EXTERNAL", "false")
    monkeypatch.setenv("AI_FOUNDATION_BRIDGE_URL", "http://127.0.0.1:8765")

    monkeypatch.setattr(
        "core.ai.providers.foundation_provider.requests.get",
        lambda *args, **kwargs: _FakeResponse(
            status_code=200,
            payload={"status": "error", "available": False, "error_code": "BRIDGE_UNAVAILABLE"},
        ),
    )
    monkeypatch.setattr(
        "core.ai.providers.foundation_provider.requests.post",
        lambda *args, **kwargs: _FakeResponse(status_code=500, payload={"ok": False}),
    )

    provider = FoundationProvider()
    result = provider.run("ingest", {"text": "테스트"})
    assert result.ok is False
    assert result.error == "BRIDGE_UNAVAILABLE"


def test_foundation_provider_timeout_maps_error_code(monkeypatch):
    monkeypatch.setenv("AI_ALLOW_EXTERNAL", "false")
    monkeypatch.setenv("AI_FOUNDATION_BRIDGE_URL", "http://127.0.0.1:8765")

    monkeypatch.setattr(
        "core.ai.providers.foundation_provider.requests.get",
        lambda *args, **kwargs: _FakeResponse(
            status_code=200,
            payload={"status": "ok", "available": True, "provider": "foundation", "version": "0.1.0"},
        ),
    )

    def _timeout(*args, **kwargs):
        raise requests.Timeout("timeout")

    monkeypatch.setattr("core.ai.providers.foundation_provider.requests.post", _timeout)

    provider = FoundationProvider()
    result = provider.run("ingest", {"text": "테스트", "timeout_ms": 50})
    assert result.ok is False
    assert result.error == "BRIDGE_TIMEOUT"


def test_foundation_provider_success_returns_contract(monkeypatch):
    monkeypatch.setenv("AI_ALLOW_EXTERNAL", "false")
    monkeypatch.setenv("AI_FOUNDATION_BRIDGE_URL", "http://127.0.0.1:8765")

    monkeypatch.setattr(
        "core.ai.providers.foundation_provider.requests.get",
        lambda *args, **kwargs: _FakeResponse(
            status_code=200,
            payload={"status": "ok", "available": True, "provider": "foundation", "version": "0.1.0"},
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
                    "summary_120": "요약",
                    "entities": [],
                    "tags": ["doc"],
                    "context_tag": "doc",
                    "confidence_model": 0.81,
                },
                "meta": {"provider": "foundation", "latency_ms": 120},
            },
        ),
    )

    provider = FoundationProvider()
    result = provider.run("ingest", {"text": "테스트"})
    assert result.ok is True
    assert result.error == ""
    assert isinstance(result.data, dict)
    assert result.data["schema"] == "ingest_contract.v0.1"
    assert result.meta["provider"] == "foundation"
