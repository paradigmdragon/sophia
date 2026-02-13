import json

import pytest

from sophia_kernel.audit import ledger as audit_ledger
from sophia_kernel.executor import executor
from sophia_kernel.registry import registry
from sophia_kernel.skills.workspace import read_file


def _register_workspace_read_file_skill(skill_id: str) -> None:
    manifest = {
        "schema_version": "0.1",
        "version": "0.1.0",
        "skill_id": skill_id,
        "scope": "workspace",
        "entrypoint": "workspace.read_file",
        "capabilities": ["fs.read", "audit.append"],
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
    workspace_root = tmp_path / "workspace_root"
    workspace_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(registry, "REGISTRY_ROOT", str(registry_root))
    monkeypatch.setattr(read_file, "WORKSPACE_ROOT", workspace_root)
    original_append = audit_ledger.append_audit_record

    def _append_to_tmp(record: dict) -> None:
        original_append(record, ledger_path=ledger_path)

    monkeypatch.setattr(executor.audit_ledger, "append_audit_record", _append_to_tmp)
    return workspace_root, ledger_path


def test_workspace_read_file_valid_file_read_returns_content(monkeypatch, tmp_path):
    workspace_root, _ = _isolate_runtime(monkeypatch, tmp_path)
    _register_workspace_read_file_skill("workspace.read_file.valid")
    sample = workspace_root / "notes.txt"
    sample.write_text("hello from workspace", encoding="utf-8")

    outputs = executor.execute_skill(
        skill_id="workspace.read_file.valid",
        version="0.1.0",
        inputs={"path": "notes.txt"},
    )

    assert outputs == {"content": "hello from workspace"}


def test_workspace_read_file_outside_root_raises(monkeypatch, tmp_path):
    _, ledger_path = _isolate_runtime(monkeypatch, tmp_path)
    _register_workspace_read_file_skill("workspace.read_file.outside")
    outside = tmp_path / "outside.txt"
    outside.write_text("denied", encoding="utf-8")

    with pytest.raises(PermissionError):
        executor.execute_skill(
            skill_id="workspace.read_file.outside",
            version="0.1.0",
            inputs={"path": str(outside)},
        )

    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["status"] == "failed"


def test_workspace_read_file_appends_committed_audit_line(monkeypatch, tmp_path):
    workspace_root, ledger_path = _isolate_runtime(monkeypatch, tmp_path)
    _register_workspace_read_file_skill("workspace.read_file.audit")
    sample = workspace_root / "audit.txt"
    sample.write_text("audit-check", encoding="utf-8")

    outputs = executor.execute_skill(
        skill_id="workspace.read_file.audit",
        version="0.1.0",
        inputs={"path": "audit.txt"},
    )

    assert outputs == {"content": "audit-check"}
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["status"] == "committed"
    assert payload["skill_id"] == "workspace.read_file.audit"
