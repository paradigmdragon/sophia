from __future__ import annotations

from pathlib import Path


WORKSPACE_ROOT = Path("/Users/dragonpd/Sophia/sophia_workspace")


def _resolve_workspace_path(raw_path: str) -> Path:
    root = WORKSPACE_ROOT.resolve()
    requested = Path(raw_path)
    target = requested if requested.is_absolute() else root / requested
    resolved = target.resolve()

    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PermissionError("path is outside workspace root") from exc

    return resolved


def run(inputs: dict) -> dict:
    raw_path = inputs.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("inputs.path is required")

    target = _resolve_workspace_path(raw_path)
    if not target.is_file():
        raise FileNotFoundError(str(target))

    return {"content": target.read_text(encoding="utf-8")}
