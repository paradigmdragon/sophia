import json

import pytest

from sophia_kernel.audit import ledger as audit_ledger
from sophia_kernel.executor import executor
from sophia_kernel.registry import registry


def test_execute_strict_fail_blocks_commit_and_writes_failed_audit(monkeypatch, tmp_path):
    registry_root = tmp_path / "registry" / "skills"
    ledger_path = tmp_path / "audit" / "ledger.jsonl"

    monkeypatch.setattr(registry, "REGISTRY_ROOT", str(registry_root))
    original_append = audit_ledger.append_audit_record

    def _append_to_tmp(record: dict) -> None:
        original_append(record, ledger_path=ledger_path)

    monkeypatch.setattr(executor.audit_ledger, "append_audit_record", _append_to_tmp)
    monkeypatch.setattr(
        executor.verifier,
        "verify",
        lambda manifest, inputs, outputs, observed_effects: {
            "pass": False,
            "violations": ["simulated strict failure"],
            "mode": "strict",
        },
    )

    manifest = {
        "schema_version": "0.1",
        "version": "0.1.0",
        "skill_id": "kernel.noop_strict",
        "scope": "engine",
        "entrypoint": "noop.ok",
        "capabilities": ["fs.write", "audit.append"],
        "verification": {"mode": "strict", "hook": "verify.default"},
        "rollback": {
            "strategy": "snapshot_restore",
            "backup_root": "/Users/dragonpd/Sophia/.sophia/backups",
        },
        "limits": {"timeout_ms": 30000, "max_retries": 0},
    }
    registry.register_skill(manifest)

    with pytest.raises(RuntimeError, match="strict verification failed"):
        executor.execute_skill(
            skill_id="kernel.noop_strict",
            version="0.1.0",
            inputs={"sample": "input"},
        )

    assert ledger_path.exists()
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["status"] == "failed"
    assert payload["skill_id"] == "kernel.noop_strict"
