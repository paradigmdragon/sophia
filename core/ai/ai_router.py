from __future__ import annotations

from typing import Any

from core.ai.gate import validate_contract
from core.ai.providers import FoundationProvider, OllamaProvider, RuleProvider


SUPPORTED_TASKS = {"ingest", "transcript", "diff", "rules", "anchor"}


class AIRouterService:
    def __init__(self, *, provider_default: str = "ollama", mode: str = "fallback") -> None:
        self.provider_default = provider_default.strip().lower() if provider_default else "ollama"
        self.mode_default = mode.strip().lower() if mode else "fallback"
        self.providers = {
            "foundation": FoundationProvider(),
            "ollama": OllamaProvider(),
            "rule": RuleProvider(),
        }

    def _provider_order(self, primary: str, mode: str) -> list[str]:
        base = primary if primary in self.providers else self.provider_default
        if base not in self.providers:
            base = "ollama"

        if mode == "single":
            return [base]

        order = [base]
        if base == "foundation":
            order.extend(["ollama", "rule"])
        elif base == "ollama":
            order.append("rule")
        elif base == "rule":
            pass
        else:
            order.append("rule")

        deduped: list[str] = []
        for item in order:
            if item in deduped:
                continue
            deduped.append(item)
        return deduped

    def run(
        self,
        *,
        task: str,
        payload: dict[str, Any],
        provider: str | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        task_key = (task or "").strip().lower()
        if task_key not in SUPPORTED_TASKS:
            raise ValueError(f"unsupported task: {task}")

        mode_key = (mode or self.mode_default or "fallback").strip().lower()
        if mode_key == "dual-run":
            raise ValueError("dual-run is disabled in phase1")
        if mode_key not in {"single", "fallback"}:
            mode_key = "fallback"

        primary = (provider or self.provider_default or "ollama").strip().lower()
        order = self._provider_order(primary, mode_key)

        attempts: list[dict[str, Any]] = []
        selected_contract: dict[str, Any] | None = None
        selected_gate: dict[str, Any] | None = None
        provider_final = "rule"

        for provider_name in order:
            runner = self.providers.get(provider_name)
            if runner is None:
                attempts.append({"provider": provider_name, "ok": False, "error": "provider_not_found"})
                continue

            result = runner.run(task_key, payload)
            attempts.append(
                {
                    "provider": provider_name,
                    "ok": bool(result.ok),
                    "available": bool(result.available),
                    "error": result.error,
                }
            )
            if not result.ok or not isinstance(result.data, dict):
                continue

            contract, gate = validate_contract(task_key, result.data)
            if bool(gate.get("fallback_applied", False)) and mode_key == "fallback" and provider_name != "rule":
                continue

            selected_contract = contract
            selected_gate = gate
            provider_final = provider_name
            break

        if selected_contract is None or selected_gate is None:
            selected_contract, selected_gate = validate_contract(task_key, {})
            provider_final = "rule"

        attempts_count = len(attempts)
        fallback_applied = (
            bool(selected_gate.get("fallback_applied", False))
            or provider_final != primary
            or attempts_count >= 2
        )

        return {
            "contract": selected_contract,
            "gate": selected_gate,
            "meta": {
                "task": task_key,
                "mode": mode_key,
                "provider_primary": primary,
                "provider_final": provider_final,
                "fallback_applied": fallback_applied,
                "attempts_count": attempts_count,
                "attempts": attempts,
            },
        }
