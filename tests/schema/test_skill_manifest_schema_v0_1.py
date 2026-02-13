import json
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "sophia_kernel" / "schema" / "skill_manifest_schema_v0_1.json"


def _load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate(schema, payload):
    validator = jsonschema.Draft202012Validator(schema)
    validator.validate(payload)


def test_minimal_manifest_advisory_ok():
    schema = _load_schema()
    manifest = {
        "schema_version": "0.1",
        "version": "0.1.0",
        "skill_id": "workspace.read_only_check",
        "scope": "workspace",
        "entrypoint": "skills.workspace.read_only_check:run",
        "capabilities": ["fs.read", "audit.append"],
        "verification": {"mode": "advisory", "hook": "verify.default"},
        "rollback": {
            "strategy": "snapshot_restore",
            "backup_root": "/Users/dragonpd/Sophia/.sophia/backups",
        },
        "limits": {"timeout_ms": 30000, "max_retries": 1},
    }
    _validate(schema, manifest)


def test_fs_write_requires_strict():
    schema = _load_schema()
    manifest = {
        "schema_version": "0.1",
        "version": "0.1.0",
        "skill_id": "workspace.write_file",
        "scope": "workspace",
        "entrypoint": "skills.workspace.write_file:run",
        "capabilities": ["fs.read", "fs.write", "audit.append"],
        "verification": {"mode": "advisory", "hook": "verify.default"},
        "rollback": {
            "strategy": "snapshot_restore",
            "backup_root": "/Users/dragonpd/Sophia/.sophia/backups",
        },
        "limits": {"timeout_ms": 30000, "max_retries": 1},
    }
    with pytest.raises(jsonschema.ValidationError):
        _validate(schema, manifest)
