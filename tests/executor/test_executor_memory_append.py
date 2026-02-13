import json

import pytest

from sophia_kernel.audit import ledger as audit_ledger
from sophia_kernel.executor import executor
from sophia_kernel.registry import registry
from sophia_kernel.skills.memory import append as memory_append


def _register_memory_append_skill(skill_id: str = "memory.append") -> None:
    manifest = {
        "schema_version": "0.1",
        "version": "0.1.0",
        "skill_id": skill_id,
        "scope": "manifest_memory",
        "entrypoint": "memory.append",
        "capabilities": ["memory.write"],
        "verification": {"mode": "advisory", "hook": "verify.default"},
        "rollback": {
            "strategy": "snapshot_restore",
            "backup_root": "/Users/dragonpd/Sophia/.sophia/backups",
        },
        "limits": {"timeout_ms": 30000, "max_retries": 0},
    }
    registry.register_skill(manifest)


def _isolate_runtime(monkeypatch, tmp_path):
    registry_root = tmp_path / "registry" / "skills"
    ledger_path = tmp_path / "audit" / "ledger.jsonl"
    memory_root = tmp_path / "sophia_workspace" / "memory"

    monkeypatch.setattr(registry, "REGISTRY_ROOT", str(registry_root))
    monkeypatch.setattr(memory_append, "MEMORY_ROOT", memory_root)
    original_append = audit_ledger.append_audit_record

    def _append_to_tmp(record: dict) -> None:
        original_append(record, ledger_path=ledger_path)

    monkeypatch.setattr(executor.audit_ledger, "append_audit_record", _append_to_tmp)
    return memory_root, ledger_path


def test_memory_append_creates_namespace_file(monkeypatch, tmp_path):
    memory_root, _ = _isolate_runtime(monkeypatch, tmp_path)
    _register_memory_append_skill()

    outputs = executor.execute_skill(
        skill_id="memory.append",
        version="0.1.0",
        inputs={"namespace": "notes", "data": {"msg": "hello"}},
    )

    assert outputs == {"namespace": "notes", "records_appended": 1}
    assert (memory_root / "notes.jsonl").exists()


def test_memory_append_appends_line(monkeypatch, tmp_path):
    memory_root, _ = _isolate_runtime(monkeypatch, tmp_path)
    _register_memory_append_skill()

    executor.execute_skill(
        skill_id="memory.append",
        version="0.1.0",
        inputs={"namespace": "skills", "data": {"a": 1}},
    )
    executor.execute_skill(
        skill_id="memory.append",
        version="0.1.0",
        inputs={"namespace": "skills", "data": {"b": 2}},
    )

    lines = (memory_root / "skills.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["data"] == {"a": 1}
    assert second["data"] == {"b": 2}
    assert "ts" in first and "ts" in second


def test_memory_append_audit_committed(monkeypatch, tmp_path):
    _, ledger_path = _isolate_runtime(monkeypatch, tmp_path)
    _register_memory_append_skill()

    executor.execute_skill(
        skill_id="memory.append",
        version="0.1.0",
        inputs={"namespace": "evolution", "data": {"state": "ok"}},
    )

    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["status"] == "committed"
    assert payload["skill_id"] == "memory.append"


def test_memory_append_invalid_input_rejected(monkeypatch, tmp_path):
    _, ledger_path = _isolate_runtime(monkeypatch, tmp_path)
    _register_memory_append_skill()

    with pytest.raises(ValueError):
        executor.execute_skill(
            skill_id="memory.append",
            version="0.1.0",
            inputs={"namespace": "../bad", "data": "not-dict"},
        )

    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["status"] == "failed"
