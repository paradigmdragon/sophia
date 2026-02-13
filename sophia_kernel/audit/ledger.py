from __future__ import annotations

import json
import os
from pathlib import Path

from jsonschema import Draft202012Validator


AUDIT_SCHEMA_PATH = Path(
    "/Users/dragonpd/Sophia/sophia_kernel/schema/audit_ledger_record_v0_1.json"
)
DEFAULT_LEDGER_PATH = Path("/Users/dragonpd/Sophia/.sophia/audit/ledger.jsonl")


def load_audit_schema() -> dict:
    return json.loads(AUDIT_SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_audit_record(record: dict) -> None:
    schema = load_audit_schema()
    Draft202012Validator(schema).validate(record)


def append_audit_record(
    record: dict, ledger_path: str | Path = DEFAULT_LEDGER_PATH
) -> None:
    validate_audit_record(record)

    target = Path(ledger_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
