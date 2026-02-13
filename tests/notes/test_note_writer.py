import json

from sophia_kernel.audit import ledger as audit_ledger
from sophia_kernel.notes import note_writer
from sophia_kernel.registry import registry
from sophia_kernel.skills.memory import append as memory_append


def _register_memory_append_skill() -> None:
    manifest = {
        "schema_version": "0.1",
        "version": "0.1.0",
        "skill_id": "memory.append",
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

    monkeypatch.setattr(note_writer.executor.audit_ledger, "append_audit_record", _append_to_tmp)
    return memory_root


def test_append_note_writes_to_correct_namespace_file(monkeypatch, tmp_path):
    memory_root = _isolate_runtime(monkeypatch, tmp_path)
    _register_memory_append_skill()

    result = note_writer.append_note(
        namespace="decisions",
        title="Choose storage model",
        body="Use append-only jsonl for MVP.",
        tags=["phase1", "mvp"],
        refs={"ticket": "SOP-101"},
    )

    assert result == {"namespace": "decisions", "records_appended": 1}
    target = memory_root / "decisions.jsonl"
    assert target.exists()


def test_append_note_appends_jsonl_line(monkeypatch, tmp_path):
    memory_root = _isolate_runtime(monkeypatch, tmp_path)
    _register_memory_append_skill()

    note_writer.append_note(namespace="actions", title="A1", body="First action")
    note_writer.append_note(namespace="actions", title="A2", body="Second action")

    target = memory_root / "actions.jsonl"
    lines = target.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2

    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["data"]["title"] == "A1"
    assert second["data"]["title"] == "A2"
    assert first["data"]["v"] == "note_v0"
    assert second["data"]["v"] == "note_v0"
