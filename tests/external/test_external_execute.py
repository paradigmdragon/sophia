import json
from typing import Any

import pytest

from sophia_kernel.skills.external.execute import RuntimeHooks, execute_external


@pytest.fixture
def manifest() -> dict[str, Any]:
    return {
        "verification": {"mode": "strict"},
        "limits": {"max_retries": 1, "max_payload_kb": 256},
        "security": {"deny_network": True, "deny_absolute_paths": True, "deny_env_access": True},
        "inputs_schema": {
            "type": "object",
            "required": ["engine", "work_id", "payload", "expected_return_schema"],
            "additionalProperties": False,
            "properties": {
                "engine": {"type": "string", "enum": ["codex", "antigravity"]},
                "work_id": {"type": "string"},
                "payload": {"type": "string"},
                "expected_return_schema": {"type": "string"},
            },
        },
        "outputs_schema": {
            "type": "object",
            "required": ["work_id", "status", "changes", "signals", "summary"],
            "additionalProperties": False,
            "properties": {
                "work_id": {"type": "string"},
                "status": {"type": "string", "enum": ["DONE", "BLOCKED", "FAILED"]},
                "changes": {"type": "array", "items": {"type": "string"}},
                "signals": {"type": "array"},
                "summary": {"type": "string"},
            },
        },
    }


@pytest.fixture
def inputs() -> dict[str, Any]:
    return {
        "engine": "codex",
        "work_id": "wp_001",
        "payload": "# Work Package 001\nDo X",
        "expected_return_schema": "report_json_v1",
    }


@pytest.fixture
def recorder():
    state = {
        "ledger": [],
        "audit": [],
        "status": [],
        "signals": [],
        "grove": [],
        "canopy": [],
        "notice": [],
    }

    hooks = RuntimeHooks(
        append_ledger_event=lambda t, p: state["ledger"].append((t, p)),
        append_audit_record=lambda r: state["audit"].append(r),
        update_work_status=lambda w, s: state["status"].append((w, s)),
        accumulate_signals=lambda sig: state["signals"].append(sig),
        trigger_grove_reanalysis=lambda w: state["grove"].append(w),
        trigger_canopy_recalc=lambda w: state["canopy"].append(w),
        notify_user=lambda m: state["notice"].append(m),
    )
    return state, hooks


def test_success_path_records_completed(manifest, inputs, recorder):
    state, hooks = recorder

    def runner(_inputs):
        return json.dumps(
            {
                "work_id": "wp_001",
                "status": "DONE",
                "changes": ["file A updated"],
                "signals": [
                    {"cluster_id": "scope_ambiguity", "hit": 1, "risk": 0.4, "evidence": "ok"}
                ],
                "summary": "done",
            },
            ensure_ascii=False,
        )

    out = execute_external(manifest, inputs, {"codex": runner}, hooks)
    assert out["status"] == "DONE"
    assert any(e[0] == "EXTERNAL_EXECUTE_STARTED" for e in state["ledger"])
    assert any(e[0] == "EXTERNAL_EXECUTE_COMPLETED" for e in state["ledger"])
    assert len(state["audit"]) >= 1


def test_retry_once_then_blocked(manifest, inputs, recorder):
    state, hooks = recorder
    calls = {"n": 0}

    def failing_runner(_inputs):
        calls["n"] += 1
        raise TimeoutError("engine timeout")

    out = execute_external(manifest, inputs, {"codex": failing_runner}, hooks)
    assert calls["n"] == 2
    assert out["status"] == "BLOCKED"
    assert any(e[0] == "EXTERNAL_EXECUTE_FAILED" for e in state["ledger"])
    assert any("외부 실행 엔진이 응답하지 않았습니다" in m for m in state["notice"])


def test_strict_output_schema_violation_blocks(manifest, inputs, recorder):
    state, hooks = recorder

    def invalid_runner(_inputs):
        return "{\"status\":\"DONE\"}"

    out = execute_external(manifest, inputs, {"codex": invalid_runner}, hooks)
    assert out["status"] == "BLOCKED"
    assert any(e[0] == "EXTERNAL_EXECUTE_FAILED" for e in state["ledger"])


def test_security_absolute_path_denied(manifest, inputs, recorder):
    _, hooks = recorder
    bad = dict(inputs)
    bad["payload"] = "read /Users/dragonpd/.ssh/id_rsa"

    out = execute_external(manifest, bad, {"codex": lambda _: "{}"}, hooks)
    assert out["status"] == "BLOCKED"
