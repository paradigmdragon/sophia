import json
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "sophia_kernel" / "schema" / "audit_ledger_record_v0_1.json"


def _load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate(schema, payload):
    validator = jsonschema.Draft202012Validator(schema)
    validator.validate(payload)


def _sha():
    return "sha256:" + ("a" * 64)


def test_audit_record_minimal_ok():
    schema = _load_schema()
    record = {
        "run_id": "run_0001",
        "skill_id": "workspace.read_only_check",
        "inputs_hash": _sha(),
        "outputs_hash": _sha(),
        "diff_refs": ["/Users/dragonpd/Sophia/.sophia/diffs/run_0001.patch"],
        "status": "committed",
        "timestamps": {
            "queued_at": "2026-02-12T10:00:00Z",
            "started_at": "2026-02-12T10:00:01Z",
            "finished_at": "2026-02-12T10:00:02Z",
        },
    }
    _validate(schema, record)


def test_audit_record_missing_required_field_fails():
    schema = _load_schema()
    record = {
        "run_id": "run_0002",
        "inputs_hash": _sha(),
        "outputs_hash": _sha(),
        "diff_refs": ["/Users/dragonpd/Sophia/.sophia/diffs/run_0002.patch"],
        "status": "failed",
        "timestamps": {
            "queued_at": "2026-02-12T10:00:00Z",
            "started_at": "2026-02-12T10:00:01Z",
            "finished_at": "2026-02-12T10:00:02Z",
        },
    }
    with pytest.raises(jsonschema.ValidationError):
        _validate(schema, record)

