import json
from pathlib import Path

from jsonschema import Draft202012Validator


SCHEMA_PATH = Path('/Users/dragonpd/Sophia/core/llm/generation_meta.schema.json')


def _validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
    return Draft202012Validator(schema)


def test_generation_meta_valid_case():
    validator = _validator()
    payload = {
        "provider": "ollama",
        "model": "llama3",
        "route": "local",
        "capabilities": {
            "web_access": False,
            "file_access": True,
            "exec_access": False,
            "device_actions": False,
        },
        "latency_ms": 12,
        "tokens_in": 10,
        "tokens_out": 20,
        "trace_id": "trace_1",
        "created_at": "2026-02-15T00:00:00Z",
    }
    assert list(validator.iter_errors(payload)) == []


def test_generation_meta_shortcuts_valid_case():
    validator = _validator()
    payload = {
        "provider": "apple_shortcuts",
        "model": "shortcut_proxy",
        "route": "proxy",
        "capabilities": {
            "web_access": False,
            "file_access": False,
            "exec_access": False,
            "device_actions": False,
        },
        "latency_ms": 7,
        "tokens_in": None,
        "tokens_out": None,
        "trace_id": "trace_shortcuts",
        "created_at": "2026-02-15T00:00:00Z",
    }
    assert list(validator.iter_errors(payload)) == []


def test_generation_meta_missing_provider_invalid():
    validator = _validator()
    payload = {
        "model": "llama3",
        "route": "local",
        "capabilities": {
            "web_access": False,
            "file_access": False,
            "exec_access": False,
            "device_actions": False,
        },
        "latency_ms": 0,
        "tokens_in": None,
        "tokens_out": None,
        "trace_id": "trace_1",
        "created_at": "2026-02-15T00:00:00Z",
    }
    assert list(validator.iter_errors(payload))


def test_generation_meta_unknown_enum_provider_invalid():
    validator = _validator()
    payload = {
        "provider": "anthropic",
        "model": "claude",
        "route": "server",
        "capabilities": {
            "web_access": True,
            "file_access": False,
            "exec_access": False,
            "device_actions": False,
        },
        "latency_ms": 20,
        "tokens_in": 1,
        "tokens_out": 1,
        "trace_id": "trace_1",
        "created_at": "2026-02-15T00:00:00Z",
    }
    assert list(validator.iter_errors(payload))


def test_generation_meta_missing_capability_field_invalid():
    validator = _validator()
    payload = {
        "provider": "mock",
        "model": "m",
        "route": "local",
        "capabilities": {
            "web_access": False,
            "file_access": False,
            "exec_access": False,
        },
        "latency_ms": 0,
        "tokens_in": None,
        "tokens_out": None,
        "trace_id": "trace_1",
        "created_at": "2026-02-15T00:00:00Z",
    }
    assert list(validator.iter_errors(payload))


def test_generation_meta_invalid_route_enum():
    validator = _validator()
    payload = {
        "provider": "openai",
        "model": "gpt",
        "route": "edge",
        "capabilities": {
            "web_access": True,
            "file_access": False,
            "exec_access": False,
            "device_actions": False,
        },
        "latency_ms": 10,
        "tokens_in": None,
        "tokens_out": None,
        "trace_id": "trace_1",
        "created_at": "2026-02-15T00:00:00Z",
    }
    assert list(validator.iter_errors(payload))


def test_generation_meta_negative_latency_invalid():
    validator = _validator()
    payload = {
        "provider": "apple",
        "model": "foundation",
        "route": "os",
        "capabilities": {
            "web_access": False,
            "file_access": False,
            "exec_access": False,
            "device_actions": True,
        },
        "latency_ms": -1,
        "tokens_in": None,
        "tokens_out": None,
        "trace_id": "trace_1",
        "created_at": "2026-02-15T00:00:00Z",
    }
    assert list(validator.iter_errors(payload))
