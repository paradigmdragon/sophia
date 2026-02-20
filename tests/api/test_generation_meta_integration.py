import hmac
import hashlib
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import chat_router
from core.memory.schema import create_session_factory


def _client(tmp_path) -> TestClient:
    db_url = f"sqlite:///{tmp_path / 'gen_meta_chat.db'}"
    chat_router.session_factory = create_session_factory(db_url)
    chat_router._legacy_backfilled = True
    app = FastAPI()
    app.include_router(chat_router.router)
    return TestClient(app)


def test_chat_messages_contains_generation_meta(monkeypatch, tmp_path):
    client = _client(tmp_path)

    def _stub_llm(_text: str, _context: dict) -> str:
        return json.dumps(
            {
                "schema": "chat_contract.v0.1",
                "kind": "ANSWER",
                "text": "범위를 확인했습니다.",
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
            "content": "상태 알려줘",
            "context_tag": "chat",
            "importance": 0.5,
            "status": "normal",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assistant = body["messages"][1]
    meta = assistant.get("meta") or {}
    generation = meta.get("generation") or {}
    ethics = meta.get("ethics") or {}

    assert generation.get("provider") in {"ollama", "mock", "unknown", "apple", "openai", "apple_shortcuts"}
    assert isinstance(generation.get("model"), str)
    assert generation.get("route") in {"local", "server", "os", "proxy"}
    caps = generation.get("capabilities") or {}
    assert set(["web_access", "file_access", "exec_access", "device_actions"]).issubset(set(caps.keys()))
    assert ethics.get("outcome") in {"ALLOW", "ADJUST", "PENDING", "BLOCK"}


def test_chat_messages_shortcuts_header_valid_signature_sets_apple_shortcuts(monkeypatch, tmp_path):
    client = _client(tmp_path)

    def _stub_llm(_text: str, _context: dict) -> str:
        return json.dumps(
            {
                "schema": "chat_contract.v0.1",
                "kind": "ANSWER",
                "text": "숏컷 경로 테스트",
                "needs": None,
                "task_plan": None,
                "sources": [{"type": "recent", "ref": "msg:latest"}],
                "confidence_model": 0.8,
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(chat_router, "_call_local_llm_contract", _stub_llm)
    monkeypatch.setattr(chat_router.settings, "shortcuts_secret", "test_shortcut_secret")
    payload = {
        "role": "user",
        "content": "Siri로 보냈어",
        "context_tag": "chat",
        "importance": 0.5,
        "status": "normal",
    }
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    signature = hmac.new(b"test_shortcut_secret", body.encode("utf-8"), hashlib.sha256).hexdigest()

    res = client.post(
        "/chat/messages",
        data=body,
        headers={
            "User-Agent": "Shortcuts/1.0",
            "X-Sophia-Source": "shortcuts",
            "X-Sophia-Shortcut-Signature": signature,
            "Content-Type": "application/json",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assistant = body["messages"][1]
    generation = (assistant.get("meta") or {}).get("generation") or {}
    assert generation.get("provider") == "apple_shortcuts"
    assert generation.get("route") == "proxy"


def test_chat_messages_shortcuts_invalid_signature_forces_unknown_and_pending(monkeypatch, tmp_path):
    client = _client(tmp_path)

    def _stub_llm(_text: str, _context: dict) -> str:
        return json.dumps(
            {
                "schema": "chat_contract.v0.1",
                "kind": "ANSWER",
                "text": "숏컷 경로 테스트",
                "needs": None,
                "task_plan": None,
                "sources": [{"type": "recent", "ref": "msg:latest"}],
                "confidence_model": 0.8,
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(chat_router, "_call_local_llm_contract", _stub_llm)
    monkeypatch.setattr(chat_router.settings, "shortcuts_secret", "test_shortcut_secret")

    payload = {
        "role": "user",
        "content": "Siri로 보냈어",
        "context_tag": "chat",
        "importance": 0.5,
        "status": "normal",
    }
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    res = client.post(
        "/chat/messages",
        data=body,
        headers={
            "User-Agent": "Shortcuts/1.0",
            "X-Sophia-Source": "shortcuts",
            "X-Sophia-Shortcut-Signature": "invalid_signature",
            "Content-Type": "application/json",
        },
    )
    assert res.status_code == 200
    assistant = res.json()["messages"][1]
    meta = assistant.get("meta") or {}
    generation = meta.get("generation") or {}
    ethics = meta.get("ethics") or {}
    assert generation.get("provider") == "unknown"
    assert generation.get("route") == "proxy"
    assert ethics.get("outcome") == "PENDING"
    assert "CAPABILITY_MISMATCH" in (ethics.get("reason_codes") or [])


def test_chat_messages_shortcuts_v11_signature_sets_apple_shortcuts(monkeypatch, tmp_path):
    client = _client(tmp_path)

    def _stub_llm(_text: str, _context: dict) -> str:
        return json.dumps(
            {
                "schema": "chat_contract.v0.1",
                "kind": "ANSWER",
                "text": "숏컷 v1.1 서명 테스트",
                "needs": None,
                "task_plan": None,
                "sources": [{"type": "recent", "ref": "msg:latest"}],
                "confidence_model": 0.8,
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(chat_router, "_call_local_llm_contract", _stub_llm)
    monkeypatch.setattr(chat_router.settings, "shortcuts_secret", "test_shortcut_secret")

    payload = {
        "role": "user",
        "content": "Siri로 v1.1",
        "context_tag": "chat",
        "importance": 0.5,
        "status": "normal",
    }
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    ts = "1739577600000"
    body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    signing_string = "\n".join(["POST", "/chat/messages", ts, body_hash])
    signature = hmac.new(b"test_shortcut_secret", signing_string.encode("utf-8"), hashlib.sha256).hexdigest()

    res = client.post(
        "/chat/messages",
        data=body,
        headers={
            "User-Agent": "Shortcuts/1.0",
            "X-Sophia-Source": "shortcuts",
            "X-Sophia-Timestamp": ts,
            "X-Sophia-Shortcut-Signature": signature,
            "Content-Type": "application/json",
        },
    )
    assert res.status_code == 200
    assistant = res.json()["messages"][1]
    generation = (assistant.get("meta") or {}).get("generation") or {}
    assert generation.get("provider") == "apple_shortcuts"
    assert generation.get("route") == "proxy"


def test_chat_messages_shortcuts_minimal_body_message_mode(monkeypatch, tmp_path):
    client = _client(tmp_path)

    def _stub_llm(_text: str, _context: dict) -> str:
        return json.dumps(
            {
                "schema": "chat_contract.v0.1",
                "kind": "ANSWER",
                "text": "DoD-A2 응답",
                "needs": None,
                "task_plan": None,
                "sources": [{"type": "recent", "ref": "msg:latest"}],
                "confidence_model": 0.8,
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(chat_router, "_call_local_llm_contract", _stub_llm)
    monkeypatch.setattr(chat_router.settings, "shortcuts_secret", "test_shortcut_secret")

    body = json.dumps({"message": "DoD-A2 probe", "mode": "chat"}, ensure_ascii=False, separators=(",", ":"))
    ts = "1739577600001"
    body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    signing_string = "\n".join(["POST", "/chat/messages", ts, body_hash])
    signature = hmac.new(b"test_shortcut_secret", signing_string.encode("utf-8"), hashlib.sha256).hexdigest()

    res = client.post(
        "/chat/messages",
        data=body,
        headers={
            "User-Agent": "Shortcuts/1.0",
            "X-Sophia-Source": "shortcuts",
            "X-Sophia-Timestamp": ts,
            "X-Sophia-Shortcut-Signature": signature,
            "Content-Type": "application/json",
        },
    )
    assert res.status_code == 200
    payload = res.json()
    assistant = payload["messages"][-1]
    generation = (assistant.get("meta") or {}).get("generation") or {}
    ethics = (assistant.get("meta") or {}).get("ethics") or {}
    assert generation.get("provider") == "apple_shortcuts"
    assert generation.get("route") == "proxy"
    assert isinstance(generation.get("trace_id"), str) and generation.get("trace_id")
    assert ethics.get("outcome") in {"ALLOW", "ADJUST", "PENDING", "BLOCK"}
