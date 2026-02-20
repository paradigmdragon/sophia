from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from jsonschema import ValidationError, validate as jsonschema_validate


class ExternalExecuteError(Exception):
    pass


@dataclass
class RuntimeHooks:
    append_ledger_event: Callable[[str, dict[str, Any]], None]
    append_audit_record: Callable[[dict[str, Any]], None]
    update_work_status: Callable[[str, str], None]
    accumulate_signals: Callable[[list[dict[str, Any]]], None]
    trigger_grove_reanalysis: Callable[[str], None]
    trigger_canopy_recalc: Callable[[str], None]
    notify_user: Callable[[str], None]


DEFAULT_INPUTS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["engine", "work_id", "payload", "expected_return_schema"],
    "properties": {
        "engine": {"type": "string", "enum": ["codex", "antigravity"]},
        "work_id": {"type": "string", "minLength": 1},
        "payload": {"type": "string", "minLength": 1, "maxLength": 262144},
        "expected_return_schema": {"type": "string", "minLength": 1},
    },
}

DEFAULT_OUTPUTS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["work_id", "status", "changes", "signals", "summary"],
    "properties": {
        "work_id": {"type": "string", "minLength": 1},
        "status": {"type": "string", "enum": ["DONE", "BLOCKED", "FAILED"]},
        "changes": {"type": "array", "items": {"type": "string"}},
        "signals": {"type": "array"},
        "summary": {"type": "string", "minLength": 1},
    },
}

_ENGINE_RUNNERS: dict[str, Callable[[dict[str, Any]], str]] = {}


def _noop_event(*_args: Any, **_kwargs: Any) -> None:
    return None


def _noop_status(*_args: Any, **_kwargs: Any) -> None:
    return None


def _noop_signals(*_args: Any, **_kwargs: Any) -> None:
    return None


def _noop_notify(*_args: Any, **_kwargs: Any) -> None:
    return None


def build_runtime_hooks() -> RuntimeHooks:
    # TODO: Bridge to Sophia API lifecycle handlers when external engine runtime is wired.
    return RuntimeHooks(
        append_ledger_event=_noop_event,
        append_audit_record=_noop_event,
        update_work_status=_noop_status,
        accumulate_signals=_noop_signals,
        trigger_grove_reanalysis=_noop_status,
        trigger_canopy_recalc=_noop_status,
        notify_user=_noop_notify,
    )


def set_engine_runner(engine: str, runner: Callable[[dict[str, Any]], str]) -> None:
    if engine not in {"codex", "antigravity"}:
        raise ValueError(f"unsupported engine: {engine}")
    _ENGINE_RUNNERS[engine] = runner


def clear_engine_runners() -> None:
    _ENGINE_RUNNERS.clear()


def _sha256_json(data: dict[str, Any]) -> str:
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _manifest_path() -> Path:
    return Path(__file__).with_name("manifest.json")


def _load_manifest() -> dict[str, Any]:
    return json.loads(_manifest_path().read_text(encoding="utf-8"))


def _normalize_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(manifest)
    verification = normalized.get("verification", {"mode": "strict"})
    if isinstance(verification, str):
        verification = {"mode": verification}
    if not isinstance(verification, dict):
        verification = {"mode": "strict"}
    normalized["verification"] = verification
    normalized.setdefault("inputs_schema", DEFAULT_INPUTS_SCHEMA)
    normalized.setdefault("outputs_schema", DEFAULT_OUTPUTS_SCHEMA)
    return normalized


def _default_engine_runners() -> dict[str, Callable[[dict[str, Any]], str]]:
    def _missing(engine: str) -> Callable[[dict[str, Any]], str]:
        def _runner(_: dict[str, Any]) -> str:
            raise ExternalExecuteError(f"{engine} runner is not configured")

        return _runner

    return {
        "codex": _missing("codex"),
        "antigravity": _missing("antigravity"),
    }


def _enforce_security(inputs: dict[str, Any], manifest: dict[str, Any]) -> None:
    payload = str(inputs.get("payload", ""))
    security = manifest.get("security", {})
    if not isinstance(security, dict):
        security = {}

    deny_absolute_paths = bool(security.get("deny_absolute_paths", True))
    if deny_absolute_paths:
        tokens = payload.replace("\n", " ").split()
        for token in tokens:
            if token.startswith("/"):
                raise PermissionError("absolute path detected in payload")
            if len(token) >= 3 and token[1] == ":" and token[2] in {"/", "\\"}:
                raise PermissionError("absolute path detected in payload")

    deny_env_access = bool(security.get("deny_env_access", True))
    if deny_env_access and any(
        marker in payload for marker in ["OPENAI_API_KEY", "AWS_SECRET", "os.environ", "PASSWORD=", "TOKEN="]
    ):
        raise PermissionError("environment variable access pattern detected")

    deny_network = bool(security.get("deny_network", True))
    if deny_network and ("http://" in payload or "https://" in payload):
        raise PermissionError("network call hint detected in payload")


def _enforce_payload_limit(inputs: dict[str, Any], manifest: dict[str, Any]) -> None:
    limits = manifest.get("limits", {})
    if not isinstance(limits, dict):
        return
    max_payload_kb = limits.get("max_payload_kb")
    if isinstance(max_payload_kb, int) and max_payload_kb > 0:
        payload = str(inputs.get("payload", ""))
        if len(payload.encode("utf-8")) > max_payload_kb * 1024:
            raise ValueError("payload exceeds max_payload_kb")


def _verification_mode(manifest: dict[str, Any]) -> str:
    verification = manifest.get("verification", {})
    if isinstance(verification, str):
        mode = verification
    elif isinstance(verification, dict):
        mode = str(verification.get("mode", "advisory"))
    else:
        mode = "advisory"
    return mode


def _validate_io(manifest: dict[str, Any], inputs: dict[str, Any], outputs: dict[str, Any]) -> None:
    jsonschema_validate(instance=inputs, schema=manifest["inputs_schema"])
    jsonschema_validate(instance=outputs, schema=manifest["outputs_schema"])
    if outputs.get("work_id") != inputs.get("work_id"):
        raise ValidationError("work_id mismatch")


def execute_external(
    manifest: dict[str, Any],
    inputs: dict[str, Any],
    engine_runners: dict[str, Callable[[dict[str, Any]], str]],
    hooks: RuntimeHooks,
) -> dict[str, Any]:
    mode = _verification_mode(manifest)
    if mode != "strict":
        raise ExternalExecuteError("verification.mode must be strict")

    run_id = f"ext_{int(time.time() * 1000)}"
    started = time.time()

    hooks.append_ledger_event(
        "EXTERNAL_EXECUTE_STARTED",
        {
            "run_id": run_id,
            "work_id": str(inputs.get("work_id", "")),
            "engine": str(inputs.get("engine", "")),
        },
    )

    inputs_hash = _sha256_json(inputs)
    engine = str(inputs.get("engine", ""))
    max_retries = int(manifest.get("limits", {}).get("max_retries", 1))

    try:
        _enforce_payload_limit(inputs, manifest)
        _enforce_security(inputs, manifest)
        jsonschema_validate(instance=inputs, schema=manifest["inputs_schema"])

        if engine not in engine_runners:
            raise ExternalExecuteError(f"unsupported engine: {engine}")

        outputs: dict[str, Any] | None = None
        for attempt in range(max_retries + 1):
            try:
                raw = engine_runners[engine](inputs)
                if not isinstance(raw, str):
                    raise TypeError("engine output must be JSON string")
                outputs = json.loads(raw)
                if not isinstance(outputs, dict):
                    raise TypeError("engine output JSON must be object")
                _validate_io(manifest, inputs, outputs)
                break
            except Exception:
                if attempt >= max_retries:
                    raise

        assert outputs is not None
        hooks.update_work_status(inputs["work_id"], outputs["status"])
        hooks.accumulate_signals(outputs.get("signals", []))
        hooks.trigger_grove_reanalysis(inputs["work_id"])
        hooks.trigger_canopy_recalc(inputs["work_id"])

        duration_ms = int((time.time() - started) * 1000)
        outputs_hash = _sha256_json(outputs)
        hooks.append_audit_record(
            {
                "run_id": run_id,
                "work_id": inputs["work_id"],
                "engine": engine,
                "inputs_hash": inputs_hash,
                "outputs_hash": outputs_hash,
                "status": outputs["status"],
                "duration_ms": duration_ms,
            }
        )
        hooks.append_ledger_event(
            "EXTERNAL_EXECUTE_COMPLETED",
            {
                "run_id": run_id,
                "work_id": inputs["work_id"],
                "engine": engine,
                "status": outputs["status"],
                "duration_ms": duration_ms,
            },
        )
        return outputs
    except Exception as exc:
        blocked = {
            "work_id": str(inputs.get("work_id", "")),
            "status": "BLOCKED",
            "changes": [],
            "signals": [],
            "summary": f"external engine failure: {type(exc).__name__}",
        }
        duration_ms = int((time.time() - started) * 1000)
        hooks.append_audit_record(
            {
                "run_id": run_id,
                "work_id": str(inputs.get("work_id", "")),
                "engine": str(inputs.get("engine", "")),
                "inputs_hash": inputs_hash,
                "outputs_hash": _sha256_json(blocked),
                "status": "BLOCKED",
                "duration_ms": duration_ms,
            }
        )
        hooks.append_ledger_event(
            "EXTERNAL_EXECUTE_FAILED",
            {
                "run_id": run_id,
                "work_id": str(inputs.get("work_id", "")),
                "engine": str(inputs.get("engine", "")),
                "error": str(exc),
                "duration_ms": duration_ms,
            },
        )
        hooks.update_work_status(str(inputs.get("work_id", "")), "BLOCKED")
        hooks.notify_user("주인님, 외부 실행 엔진이 응답하지 않았습니다. 재시도하시겠습니까?")
        return blocked


def run(
    inputs: dict[str, Any],
    manifest: dict[str, Any] | None = None,
    engine_runners: dict[str, Callable[[dict[str, Any]], str]] | None = None,
    hooks: RuntimeHooks | None = None,
) -> dict[str, Any]:
    effective_manifest = _normalize_manifest(manifest or _load_manifest())
    if engine_runners is not None:
        runners = engine_runners
    elif _ENGINE_RUNNERS:
        runners = dict(_ENGINE_RUNNERS)
    else:
        runners = _default_engine_runners()
    effective_hooks = hooks or build_runtime_hooks()
    return execute_external(effective_manifest, inputs, runners, effective_hooks)
