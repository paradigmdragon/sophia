from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from sophia_kernel.audit import ledger as audit_ledger
from sophia_kernel.registry import registry
from sophia_kernel.verifier import verifier


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha256_json(value: dict) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _verifier_diff_ref(report: dict) -> str:
    mode = report.get("mode", "unknown")
    passed = str(bool(report.get("pass", False))).lower()
    violations = report.get("violations", [])
    count = len(violations) if isinstance(violations, list) else 0
    return f"verifier://mode={mode};pass={passed};violations={count}"


def _error_diff_ref(exc: Exception) -> str:
    return f"error://type={type(exc).__name__};message={str(exc)}"


def _skill_id(manifest: dict) -> str:
    skill_id = manifest.get("skill_id", manifest.get("id"))
    if not isinstance(skill_id, str) or not skill_id:
        raise KeyError("manifest skill id is required")
    return skill_id


def _verification_mode(manifest: dict) -> str:
    raw = manifest.get("verification", {})
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        return str(raw.get("mode", "advisory"))
    return "advisory"


def resolve_entrypoint(entrypoint: str, manifest: dict | None = None):
    if entrypoint == "external.execute":
        from sophia_kernel.skills.external import execute as external_execute

        def _external_run(inputs: dict) -> dict:
            return external_execute.run(inputs=inputs, manifest=manifest)

        return _external_run

    if entrypoint == "memory.append":
        from sophia_kernel.skills.memory import append

        return append.run

    if entrypoint == "workspace.write_file":
        from sophia_kernel.skills.workspace import write_file

        return write_file.run

    if entrypoint == "workspace.read_file":
        from sophia_kernel.skills.workspace import read_file

        return read_file.run

    if entrypoint != "noop.ok":
        raise ValueError(f"unsupported entrypoint: {entrypoint}")

    def _noop_ok(_: dict) -> dict:
        return {"ok": True}

    return _noop_ok


def execute_skill(skill_id: str, version: str, inputs: dict) -> dict:
    manifest = registry.get_skill(skill_id, version)

    capabilities = set(manifest.get("capabilities", []))
    verification_mode = _verification_mode(manifest)
    needs_strict = (
        "fs.write" in capabilities
        or "manifest.write" in capabilities
        or "external.run" in capabilities
    )
    if needs_strict and verification_mode != "strict":
        raise PermissionError("strict verification is required for write capabilities")

    queued_at = _utc_now()
    started_at = _utc_now()
    run_id = f"run_{uuid4()}"

    runner = resolve_entrypoint(manifest["entrypoint"], manifest=manifest)
    skill_manifest_id = _skill_id(manifest)
    try:
        outputs = runner(inputs)
    except Exception as exc:
        finished_at = _utc_now()
        error_output = {"error": {"type": type(exc).__name__, "message": str(exc)}}
        record = {
            "schema_version": "0.1",
            "run_id": run_id,
            "skill_id": skill_manifest_id,
            "inputs_hash": _sha256_json(inputs),
            "outputs_hash": _sha256_json(error_output),
            "diff_refs": [_error_diff_ref(exc)],
            "status": "failed",
            "timestamps": {
                "queued_at": queued_at,
                "started_at": started_at,
                "finished_at": finished_at,
            },
        }
        audit_ledger.append_audit_record(record)
        raise

    report = verifier.verify(
        manifest=manifest,
        inputs=inputs,
        outputs=outputs,
        observed_effects={},
    )
    mode = report["mode"]
    passed = report["pass"]
    if mode == "strict" and not passed:
        status = "failed"
    else:
        status = "committed"

    finished_at = _utc_now()
    record = {
        "schema_version": "0.1",
        "run_id": run_id,
        "skill_id": skill_manifest_id,
        "inputs_hash": _sha256_json(inputs),
        "outputs_hash": _sha256_json(outputs),
        "diff_refs": [_verifier_diff_ref(report)],
        "status": status,
        "timestamps": {
            "queued_at": queued_at,
            "started_at": started_at,
            "finished_at": finished_at,
        },
    }
    audit_ledger.append_audit_record(record)

    if mode == "strict" and not passed:
        raise RuntimeError("strict verification failed")

    return outputs
