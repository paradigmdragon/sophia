import json

from sophia_kernel.audit import ledger as audit_ledger
from sophia_kernel.executor import executor
from sophia_kernel.registry import registry
from sophia_kernel.skills.external import execute as external_execute


def test_executor_external_execute_resolves_and_runs(monkeypatch, tmp_path):
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
        "skill_id": "external.execute",
        "scope": "engine",
        "entrypoint": "external.execute",
        "capabilities": ["external.run", "audit.append"],
        "verification": {"mode": "strict", "hook": "verify.default"},
        "rollback": {
            "strategy": "snapshot_restore",
            "backup_root": "/Users/dragonpd/Sophia/.sophia/backups",
        },
        "limits": {"timeout_ms": 120000, "max_retries": 1},
    }
    registry.register_skill(manifest)

    external_execute.clear_engine_runners()
    external_execute.set_engine_runner(
        "codex",
        lambda _: json.dumps(
            {
                "work_id": "wp_external_001",
                "status": "DONE",
                "changes": ["external skill smoke"],
                "signals": [],
                "summary": "ok",
            }
        ),
    )

    try:
        outputs = executor.execute_skill(
            skill_id="external.execute",
            version="0.1.0",
            inputs={
                "engine": "codex",
                "work_id": "wp_external_001",
                "payload": "# Work Package external smoke",
                "expected_return_schema": "report_json_v1",
            },
        )
    finally:
        external_execute.clear_engine_runners()

    assert outputs["status"] == "DONE"
    assert ledger_path.exists()
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["skill_id"] == "external.execute"
