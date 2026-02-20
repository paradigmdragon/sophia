from __future__ import annotations

import hashlib
import json
from typing import Literal

RecordCategory = Literal[
    "SYSTEM_CHANGE",
    "PROBLEM_FIX",
    "FEATURE_ADD",
    "UI_CHANGE",
    "DOC_CHANGE",
    "CHORE",
]

TRACKED_CATEGORIES: set[str] = {
    "SYSTEM_CHANGE",
    "PROBLEM_FIX",
    "FEATURE_ADD",
}

PROBLEM_KEYWORDS = {
    "fix",
    "bug",
    "error",
    "fail",
    "failed",
    "block",
    "blocked",
    "issue",
    "hotfix",
    "문제",
    "오류",
    "버그",
    "수정",
}
FEATURE_KEYWORDS = {
    "feature",
    "add",
    "new",
    "implement",
    "introduce",
    "추가",
    "도입",
    "구현",
}


def _normalize_path(value: str) -> str:
    return str(value or "").strip().replace("\\", "/").lower()


def _is_ui_path(path: str) -> bool:
    return path.startswith("apps/desktop/") or "/apps/desktop/" in path


def _is_system_path(path: str) -> bool:
    prefixes = (
        "api/",
        "core/",
        "sophia_kernel/",
        "scripts/",
        "kernel/",
        "tests/",
    )
    return path.startswith(prefixes)


def _is_doc_path(path: str) -> bool:
    return path.startswith(("docs/", "spec/"))


def classify_record_entry(
    *,
    title: str,
    summary: str = "",
    files: list[str] | None = None,
    tags: list[str] | None = None,
    category_hint: str = "",
) -> tuple[RecordCategory, str]:
    hint = str(category_hint or "").strip().upper()
    if hint in {"SYSTEM_CHANGE", "PROBLEM_FIX", "FEATURE_ADD", "UI_CHANGE", "DOC_CHANGE", "CHORE"}:
        return hint, "hint"

    file_rows = [_normalize_path(row) for row in (files or []) if _normalize_path(row)]
    has_ui = any(_is_ui_path(row) for row in file_rows)
    has_system = any(_is_system_path(row) for row in file_rows)
    has_docs = any(_is_doc_path(row) for row in file_rows)
    only_ui = bool(file_rows) and all(_is_ui_path(row) for row in file_rows)
    only_docs = bool(file_rows) and all(_is_doc_path(row) for row in file_rows)

    text = f"{title} {summary} {' '.join(tags or [])}".lower()
    if any(keyword in text for keyword in PROBLEM_KEYWORDS):
        if has_ui and not has_system:
            return "UI_CHANGE", "ui_problem"
        return "PROBLEM_FIX", "keyword_problem"
    if any(keyword in text for keyword in FEATURE_KEYWORDS):
        if has_ui and not has_system:
            return "UI_CHANGE", "ui_feature"
        return "FEATURE_ADD", "keyword_feature"

    if has_system:
        return "SYSTEM_CHANGE", "system_path"
    if only_ui:
        return "UI_CHANGE", "ui_path"
    if only_docs or has_docs:
        return "DOC_CHANGE", "doc_path"
    return "CHORE", "fallback"


def should_record_entry(category: str, *, force: bool = False) -> bool:
    if force:
        return True
    return str(category or "").upper() in TRACKED_CATEGORIES


def make_record_fingerprint(
    *,
    project: str,
    category: str,
    title: str,
    summary: str,
    files: list[str] | None = None,
) -> str:
    payload = {
        "project": str(project or "").strip().lower(),
        "category": str(category or "").strip().upper(),
        "title": str(title or "").strip(),
        "summary": str(summary or "").strip(),
        "files": sorted([_normalize_path(row) for row in (files or []) if _normalize_path(row)]),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
