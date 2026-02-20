from __future__ import annotations

import os
import time
from typing import Any
from urllib.parse import urlparse

import requests

from core.ai.gate import validate_contract
from core.ai.providers.base import BaseProvider, ProviderResult


_DEFAULT_BRIDGE_URL = "http://127.0.0.1:8765"
_DEFAULT_TIMEOUT_MS = 3000
_ALLOWED_LOCAL_HOSTS = {"127.0.0.1", "localhost"}
_ERROR_CODES = {
    "BRIDGE_TIMEOUT",
    "BRIDGE_UNAVAILABLE",
    "BRIDGE_SCHEMA_MISMATCH",
    "BRIDGE_HOST_BLOCKED",
    "BRIDGE_NETWORK_ERROR",
}
_SCHEMA_BY_TASK = {
    "ingest": "ingest_contract.v0.1",
    "transcript": "transcript_contract.v0.1",
    "diff": "diff_contract.v0.1",
    "rules": "rule_candidate.v0.1",
    "anchor": "anchor_candidate.v0.1",
}


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(str(raw).strip())
    except ValueError:
        return default
    return value if value > 0 else default


class FoundationProvider(BaseProvider):
    name = "foundation"

    def __init__(self, *, bridge_url: str | None = None, timeout_ms: int | None = None) -> None:
        self._bridge_url_default = bridge_url or _DEFAULT_BRIDGE_URL
        self._timeout_ms_default = timeout_ms if isinstance(timeout_ms, int) and timeout_ms > 0 else _DEFAULT_TIMEOUT_MS

    def _bridge_url(self) -> str:
        value = os.getenv("AI_FOUNDATION_BRIDGE_URL", self._bridge_url_default)
        return str(value).strip().rstrip("/") or _DEFAULT_BRIDGE_URL

    def _allow_external(self) -> bool:
        return _env_bool("AI_ALLOW_EXTERNAL", False)

    def _timeout_ms(self, payload: dict[str, Any]) -> int:
        payload_timeout = payload.get("timeout_ms")
        if isinstance(payload_timeout, int) and payload_timeout > 0:
            return payload_timeout
        return _env_int("AI_FOUNDATION_TIMEOUT_MS", self._timeout_ms_default)

    def _is_host_allowed(self, bridge_url: str) -> bool:
        parsed = urlparse(bridge_url)
        host = (parsed.hostname or "").strip().lower()
        if self._allow_external():
            return True
        return host in _ALLOWED_LOCAL_HOSTS

    def _fail(self, *, code: str, available: bool, message: str = "", meta: dict[str, Any] | None = None) -> ProviderResult:
        error_code = code if code in _ERROR_CODES else "BRIDGE_NETWORK_ERROR"
        merged_meta = dict(meta or {})
        if message:
            merged_meta.setdefault("message", message)
        return ProviderResult(
            provider=self.name,
            ok=False,
            available=available,
            error=error_code,
            meta=merged_meta,
        )

    def run(self, task: str, payload: dict) -> ProviderResult:
        task_key = str(task or "").strip().lower()
        contract_schema = _SCHEMA_BY_TASK.get(task_key)
        bridge_url = self._bridge_url()
        timeout_ms = self._timeout_ms(payload)
        timeout_s = max(0.1, timeout_ms / 1000.0)

        if not contract_schema:
            return self._fail(
                code="BRIDGE_SCHEMA_MISMATCH",
                available=False,
                message=f"unsupported task: {task_key}",
                meta={"bridge_url": bridge_url, "task": task_key},
            )

        if not self._is_host_allowed(bridge_url):
            return self._fail(
                code="BRIDGE_HOST_BLOCKED",
                available=False,
                message="bridge host must be localhost or 127.0.0.1 when AI_ALLOW_EXTERNAL=false",
                meta={"bridge_url": bridge_url, "task": task_key},
            )

        health_url = f"{bridge_url}/bridge/health"
        run_url = f"{bridge_url}/bridge/run"
        latency_ms = 0

        try:
            health_started = time.perf_counter()
            health_res = requests.get(health_url, timeout=timeout_s)
            health_elapsed_ms = int((time.perf_counter() - health_started) * 1000)
            if health_res.status_code != 200:
                return self._fail(
                    code="BRIDGE_UNAVAILABLE",
                    available=False,
                    message=f"health status={health_res.status_code}",
                    meta={"bridge_url": bridge_url, "health_latency_ms": health_elapsed_ms, "task": task_key},
                )
            try:
                health_payload = health_res.json()
            except ValueError:
                return self._fail(
                    code="BRIDGE_UNAVAILABLE",
                    available=False,
                    message="health endpoint did not return JSON",
                    meta={"bridge_url": bridge_url, "health_latency_ms": health_elapsed_ms, "task": task_key},
                )
            if not bool(health_payload.get("available", False)):
                return self._fail(
                    code="BRIDGE_UNAVAILABLE",
                    available=False,
                    message=str(health_payload.get("error_code") or "bridge unavailable"),
                    meta={"bridge_url": bridge_url, "health_latency_ms": health_elapsed_ms, "task": task_key},
                )

            request_payload = {
                "task": task_key,
                "contract_schema": contract_schema,
                "input": dict(payload),
                "timeout_ms": timeout_ms,
            }
            started = time.perf_counter()
            run_res = requests.post(run_url, json=request_payload, timeout=timeout_s)
            latency_ms = int((time.perf_counter() - started) * 1000)
        except requests.Timeout:
            return self._fail(
                code="BRIDGE_TIMEOUT",
                available=False,
                message="bridge request timed out",
                meta={"bridge_url": bridge_url, "task": task_key, "timeout_ms": timeout_ms},
            )
        except requests.RequestException as exc:
            return self._fail(
                code="BRIDGE_NETWORK_ERROR",
                available=False,
                message=str(exc),
                meta={"bridge_url": bridge_url, "task": task_key},
            )

        try:
            run_payload = run_res.json()
        except ValueError:
            return self._fail(
                code="BRIDGE_SCHEMA_MISMATCH",
                available=True,
                message="bridge run response is not JSON",
                meta={"bridge_url": bridge_url, "task": task_key, "status_code": run_res.status_code},
            )

        if run_res.status_code != 200:
            error_code = str(run_payload.get("error_code") or "BRIDGE_UNAVAILABLE")
            return self._fail(
                code=error_code,
                available=False,
                message=str(run_payload.get("message") or f"bridge status={run_res.status_code}"),
                meta={"bridge_url": bridge_url, "task": task_key, "latency_ms": latency_ms},
            )

        if not bool(run_payload.get("ok", False)):
            error_code = str(run_payload.get("error_code") or "BRIDGE_UNAVAILABLE")
            return self._fail(
                code=error_code,
                available=False,
                message=str(run_payload.get("message") or "bridge returned ok=false"),
                meta={"bridge_url": bridge_url, "task": task_key, "latency_ms": latency_ms},
            )

        contract_candidate = run_payload.get("contract")
        contract, gate = validate_contract(task_key, contract_candidate)
        if bool(gate.get("fallback_applied", False)):
            return self._fail(
                code="BRIDGE_SCHEMA_MISMATCH",
                available=True,
                message="bridge contract failed schema validation",
                meta={
                    "bridge_url": bridge_url,
                    "task": task_key,
                    "latency_ms": latency_ms,
                    "validation_errors": list(gate.get("validation_errors", [])),
                },
            )

        returned_meta = run_payload.get("meta")
        bridge_meta = dict(returned_meta) if isinstance(returned_meta, dict) else {}
        bridge_meta.setdefault("provider", "foundation")
        bridge_meta.setdefault("latency_ms", latency_ms)
        bridge_meta.setdefault("bridge_url", bridge_url)
        bridge_meta.setdefault("timeout_ms", timeout_ms)

        return ProviderResult(
            provider=self.name,
            ok=True,
            data=contract,
            available=True,
            meta=bridge_meta,
        )
