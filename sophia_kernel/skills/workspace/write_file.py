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
    content = inputs.get("content")
    mode = inputs.get("mode", "overwrite")

    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("inputs.path is required")
    if not isinstance(content, str):
        raise ValueError("inputs.content must be a string")
    if mode not in {"overwrite", "append"}:
        raise ValueError("inputs.mode must be overwrite or append")

    target = _resolve_workspace_path(raw_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    if mode == "overwrite":
        target.write_text(content, encoding="utf-8")
    else:
        with target.open("a", encoding="utf-8") as f:
            f.write(content)

    return {"path": str(target), "bytes_written": len(content.encode("utf-8"))}
