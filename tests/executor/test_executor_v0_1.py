import json

from sophia_kernel.audit import ledger as audit_ledger
from sophia_kernel.executor import executor
from sophia_kernel.registry import registry


def test_execute_noop_skill_writes_audit_line(monkeypatch, tmp_path):
    registry_root = tmp_path / "registry" / "skills"
    ledger_path = tmp_path / "audit" / "ledger.jsonl"

    monkeypatch.setattr(registry, "REGISTRY_ROOT", str(registry_root))
    original_append = audit_ledger.append_audit_record

    def _append_to_tmp(record: dict) -> None:
        original_append(record, ledger_path=ledger_path)

    monkeypatch.setattr(executor.audit_ledger, "append_audit_record", _append_to_tmp)

    manifest = {
        "schema_version": "0.1",
        "version": "0.1.0",
        "skill_id": "kernel.noop_ok",
        "scope": "engine",
        "entrypoint": "noop.ok",
        "capabilities": ["audit.append"],
        "verification": {"mode": "advisory", "hook": "verify.default"},
        "rollback": {
            "strategy": "snapshot_restore",
            "backup_root": "/Users/dragonpd/Sophia/.sophia/backups",
        },
        "limits": {"timeout_ms": 30000, "max_retries": 0},
    }
    registry.register_skill(manifest)

    outputs = executor.execute_skill(
        skill_id="kernel.noop_ok",
        version="0.1.0",
        inputs={"sample": "input"},
    )

    assert outputs.get("ok") is True
    assert ledger_path.exists()
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["skill_id"] == "kernel.noop_ok"
