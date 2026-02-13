from __future__ import annotations

from sophia_kernel.executor import executor


ALLOWED_NAMESPACES = {"notes", "ideas", "decisions", "actions"}


def append_note(
    namespace: str,
    title: str,
    body: str,
    tags: list[str] | None = None,
    refs: dict | None = None,
) -> dict:
    if namespace not in ALLOWED_NAMESPACES:
        raise ValueError(f"namespace must be one of: {sorted(ALLOWED_NAMESPACES)}")
    if not isinstance(title, str) or not title:
        raise ValueError("title must be a non-empty string")
    if not isinstance(body, str) or not body:
        raise ValueError("body must be a non-empty string")

    data = {
        "title": title,
        "body": body,
        "tags": tags or [],
        "refs": refs or {},
        "v": "note_v0",
    }
    return executor.execute_skill(
        "memory.append",
        "0.1.0",
        {"namespace": namespace, "data": data},
    )
