#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path

warnings.filterwarnings("ignore", category=SyntaxWarning)


@dataclass
class Candidate:
    file_path: Path
    module_path: str
    app_name: str
    score: int


def _is_fastapi_call(call: ast.Call, fastapi_names: set[str]) -> bool:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id in fastapi_names
    if isinstance(func, ast.Attribute):
        return func.attr == "FastAPI"
    return False


def _extract_assignments(tree: ast.AST, fastapi_names: set[str]) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            if not _is_fastapi_call(node.value, fastapi_names):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.append(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.value, ast.Call):
            if not _is_fastapi_call(node.value, fastapi_names):
                continue
            if isinstance(node.target, ast.Name):
                names.append(node.target.id)
    return names


def _score_candidate(rel_path: Path, app_name: str, source: str) -> int:
    score = 0
    parts = set(rel_path.parts)
    if "api" in parts:
        score += 40
    if app_name == "app":
        score += 30
    if rel_path.name in {"server.py", "main.py", "app.py"}:
        score += 20
    if "include_router(" in source:
        score += 15
    if "if __name__ == \"__main__\"" in source:
        score += 5
    if "tests" in parts:
        score -= 80
    if "scripts" in parts:
        score -= 40
    if "venv" in parts or ".venv" in parts:
        score -= 100
    return score


def _module_from_path(rel_path: Path) -> str:
    return ".".join(rel_path.with_suffix("").parts)


def find_best_asgi_app(project_root: Path) -> Candidate:
    candidates: list[Candidate] = []
    skip_dirs = {".git", ".venv", "__pycache__", ".pytest_cache"}
    prioritized_files: list[Path] = []

    for rel in [Path("api"), Path("app"), Path("main.py")]:
        target = project_root / rel
        if target.is_file():
            prioritized_files.append(target)
        elif target.is_dir():
            prioritized_files.extend(target.rglob("*.py"))

    scan_files = prioritized_files if prioritized_files else list(project_root.rglob("*.py"))
    seen: set[Path] = set()

    for file_path in scan_files:
        if file_path in seen:
            continue
        seen.add(file_path)
        if any(part in skip_dirs for part in file_path.parts):
            continue
        try:
            source = file_path.read_text(encoding="utf-8")
        except OSError:
            continue

        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        fastapi_names = {"FastAPI"}
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "fastapi":
                for alias in node.names:
                    if alias.name == "FastAPI":
                        fastapi_names.add(alias.asname or alias.name)

        app_names = _extract_assignments(tree, fastapi_names)
        if not app_names:
            continue

        rel_path = file_path.relative_to(project_root)
        for app_name in app_names:
            score = _score_candidate(rel_path, app_name, source)
            candidates.append(
                Candidate(
                    file_path=rel_path,
                    module_path=_module_from_path(rel_path),
                    app_name=app_name,
                    score=score,
                )
            )

    if not candidates:
        raise RuntimeError("No FastAPI ASGI app candidate found")

    # Highest score wins; tie-break by shortest module path then lexicographic path
    candidates.sort(key=lambda c: (-c.score, len(c.module_path), str(c.file_path)))
    return candidates[0]


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    try:
        winner = find_best_asgi_app(root)
    except Exception as exc:  # pragma: no cover - defensive path
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"{winner.module_path}:{winner.app_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
