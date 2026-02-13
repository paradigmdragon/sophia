import json

import pytest

from sophia_kernel.audit import ledger as audit_ledger
from sophia_kernel.executor import executor


def _wire_tmp_ledger(monkeypatch, tmp_path):
    ledger_path = tmp_path / "audit" / "ledger.jsonl"
    original_append = audit_ledger.append_audit_record

    def _append_to_tmp(record: dict) -> None:
        original_append(record, ledger_path=ledger_path)

    monkeypatch.setattr(executor.audit_ledger, "append_audit_record", _append_to_tmp)
    return ledger_path


def test_executor_strict_skill_fails_and_writes_failed_audit(monkeypatch, tmp_path):
    ledger_path = _wire_tmp_ledger(monkeypatch, tmp_path)
    strict_manifest = {
        "schema_version": "0.1",
        "version": "0.1.0",
        "skill_id": "kernel.noop_ok_strict",
        "scope": "engine",
        "entrypoint": "noop.ok",
        "capabilities": ["audit.append"],
        "verification": {"mode": "strict", "hook": "verify.default"},
        "outputs_schema": {
            "type": "object",
            "required": ["must_exist"],
            "properties": {"must_exist": {"type": "string"}},
            "additionalProperties": True,
        },
        "rollback": {
            "strategy": "snapshot_restore",
            "backup_root": "/Users/dragonpd/Sophia/.sophia/backups",
        },
        "limits": {"timeout_ms": 30000, "max_retries": 0},
    }
    monkeypatch.setattr(executor.registry, "get_skill", lambda skill_id, version: strict_manifest)

    with pytest.raises(RuntimeError, match="strict verification failed"):
        executor.execute_skill(
            skill_id="kernel.noop_ok_strict",
            version="0.1.0",
            inputs={"sample": "input"},
        )

    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["status"] == "failed"
    assert payload["skill_id"] == "kernel.noop_ok_strict"
    assert payload["diff_refs"][0].startswith("verifier://")


def test_executor_advisory_skill_commits_and_writes_committed_audit(monkeypatch, tmp_path):
    ledger_path = _wire_tmp_ledger(monkeypatch, tmp_path)
    advisory_manifest = {
        "schema_version": "0.1",
        "version": "0.1.0",
        "skill_id": "kernel.noop_ok_advisory",
        "scope": "engine",
        "entrypoint": "noop.ok",
        "capabilities": ["audit.append"],
        "verification": {"mode": "advisory", "hook": "verify.default"},
        "outputs_schema": {
            "type": "object",
            "required": ["must_exist"],
            "properties": {"must_exist": {"type": "string"}},
            "additionalProperties": True,
        },
        "rollback": {
            "strategy": "snapshot_restore",
            "backup_root": "/Users/dragonpd/Sophia/.sophia/backups",
        },
        "limits": {"timeout_ms": 30000, "max_retries": 0},
    }
    monkeypatch.setattr(executor.registry, "get_skill", lambda skill_id, version: advisory_manifest)

    outputs = executor.execute_skill(
        skill_id="kernel.noop_ok_advisory",
        version="0.1.0",
        inputs={"sample": "input"},
    )

    assert outputs == {"ok": True}
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["status"] == "committed"
    assert payload["skill_id"] == "kernel.noop_ok_advisory"
    assert payload["diff_refs"][0].startswith("verifier://")
