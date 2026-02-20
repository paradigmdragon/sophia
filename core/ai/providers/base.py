from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderResult:
    provider: str
    ok: bool
    data: dict[str, Any] | None = None
    error: str = ""
    available: bool = True
    meta: dict[str, Any] = field(default_factory=dict)


class BaseProvider:
    name = "base"

    def run(self, task: str, payload: dict[str, Any]) -> ProviderResult:
        raise NotImplementedError
