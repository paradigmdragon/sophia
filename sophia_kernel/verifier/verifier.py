from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


def _violation(code: str, message: str, evidence: dict | None = None) -> dict:
    return {"code": code, "message": message, "evidence": evidence or {}}


def _schema_violation(code: str, exc: ValidationError) -> dict:
    return _violation(
        code=code,
        message=exc.message,
        evidence={
            "path": list(exc.path),
            "schema_path": list(exc.schema_path),
        },
    )


def _collect_observed_violations(observed_effects: dict[str, Any]) -> list[dict]:
    raw = observed_effects.get("violations", [])
    if not isinstance(raw, list):
        raw = [raw]

    violations: list[dict] = []
    for item in raw:
        if isinstance(item, dict):
            violations.append(
                _violation(
                    code=str(item.get("code", "V_OBSERVED_EFFECT")),
                    message=str(item.get("message", "observed violation")),
                    evidence=item.get("evidence", {}),
                )
            )
        else:
            violations.append(
                _violation(
                    code="V_OBSERVED_EFFECT",
                    message=str(item),
                    evidence={},
                )
            )
    return violations


def verify(
    manifest: dict, inputs: dict, outputs: dict, observed_effects: dict | None = None
) -> dict:
    mode = manifest.get("verification", {}).get("mode", "advisory")
    if mode not in {"advisory", "strict"}:
        raise ValueError(f"unsupported verification mode: {mode}")

    violations: list[dict] = []
    observed = observed_effects or {}

    if not isinstance(outputs, dict):
        violations.append(
            _violation(
                code="V_REQUIRED_FIELDS",
                message="outputs must be a dict",
                evidence={"output_type": type(outputs).__name__},
            )
        )

    inputs_schema = manifest.get("inputs_schema")
    if isinstance(inputs_schema, dict):
        try:
            Draft202012Validator(inputs_schema).validate(inputs)
        except ValidationError as exc:
            violations.append(_schema_violation("V_INPUT_SCHEMA", exc))

    outputs_schema = manifest.get("outputs_schema")
    if isinstance(outputs_schema, dict):
        try:
            Draft202012Validator(outputs_schema).validate(outputs)
        except ValidationError as exc:
            violations.append(_schema_violation("V_OUT_SCHEMA", exc))

    violations.extend(_collect_observed_violations(observed))

    if mode == "advisory":
        passed = True
    else:
        passed = len(violations) == 0

    return {
        "pass": passed,
        "mode": mode,
        "violations": violations,
        "evidence": {
            "violation_count": len(violations),
            "observed_effects": observed,
        },
    }
