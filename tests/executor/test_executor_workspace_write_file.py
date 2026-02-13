import json

import pytest

from sophia_kernel.audit import ledger as audit_ledger
from sophia_kernel.executor import executor
from sophia_kernel.registry import registry
from sophia_kernel.skills.workspace import write_file


def _register_workspace_write_file_skill(skill_id: str, mode: str = "strict") -> None:
    manifest = {
        "schema_version": "0.1",
        "version": "0.1.0",
        "skill_id": skill_id,
        "scope": "workspace",
        "entrypoint": "workspace.write_file",
        "capabilities": ["fs.write", "audit.append"],
        "verification": {"mode": mode, "hook": "verify.default"},
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
    monkeypatch.setattr(write_file, "WORKSPACE_ROOT", workspace_root)
    original_append = audit_ledger.append_audit_record

    def _append_to_tmp(record: dict) -> None:
        original_append(record, ledger_path=ledger_path)

    monkeypatch.setattr(executor.audit_ledger, "append_audit_record", _append_to_tmp)
    return workspace_root, ledger_path


def test_write_file_strict_valid(monkeypatch, tmp_path):
    workspace_root, ledger_path = _isolate_runtime(monkeypatch, tmp_path)
    _register_workspace_write_file_skill("workspace.write_file.strict_valid", mode="strict")

    outputs = executor.execute_skill(
        skill_id="workspace.write_file.strict_valid",
        version="0.1.0",
        inputs={"path": "nested/out.txt", "content": "hello", "mode": "overwrite"},
    )

    target = workspace_root / "nested" / "out.txt"
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "hello"
    assert outputs["path"] == str(target.resolve())
    assert outputs["bytes_written"] == len("hello".encode("utf-8"))

    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["status"] == "committed"


def test_write_file_outside_root_denied(monkeypatch, tmp_path):
    _, ledger_path = _isolate_runtime(monkeypatch, tmp_path)
    _register_workspace_write_file_skill("workspace.write_file.outside", mode="strict")
    outside = tmp_path / "outside.txt"

    with pytest.raises(PermissionError):
        executor.execute_skill(
            skill_id="workspace.write_file.outside",
            version="0.1.0",
            inputs={"path": str(outside), "content": "denied", "mode": "overwrite"},
        )

    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["status"] == "failed"


def test_write_file_requires_strict(monkeypatch, tmp_path):
    workspace_root, ledger_path = _isolate_runtime(monkeypatch, tmp_path)
    invalid_manifest = {
        "schema_version": "0.1",
        "version": "0.1.0",
        "skill_id": "workspace.write_file.requires_strict",
        "scope": "workspace",
        "entrypoint": "workspace.write_file",
        "capabilities": ["fs.write", "audit.append"],
        "verification": {"mode": "advisory", "hook": "verify.default"},
        "rollback": {
            "strategy": "snapshot_restore",
            "backup_root": "/Users/dragonpd/Sophia/.sophia/backups",
        },
        "limits": {"timeout_ms": 30000, "max_retries": 0},
    }
    monkeypatch.setattr(executor.registry, "get_skill", lambda skill_id, version: invalid_manifest)

    target = workspace_root / "blocked.txt"
    with pytest.raises(PermissionError, match="strict verification is required"):
        executor.execute_skill(
            skill_id="workspace.write_file.requires_strict",
            version="0.1.0",
            inputs={"path": "blocked.txt", "content": "should-not-write"},
        )

    assert not target.exists()
    assert not ledger_path.exists()
