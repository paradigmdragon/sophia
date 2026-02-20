#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib import error, request

DEFAULT_BASE_URL = "http://127.0.0.1:8090"
REPO_ROOT = Path(__file__).resolve().parent.parent
TRACKED_CATEGORIES = {"SYSTEM_CHANGE", "PROBLEM_FIX", "FEATURE_ADD"}


class SyncLoopError(RuntimeError):
    pass


def _parse_items_file(path: str | None) -> list[dict[str, Any]]:
    if not path:
        return []
    source = Path(path)
    if not source.exists() or not source.is_file():
        raise SyncLoopError(f"items file not found: {source}")
    try:
        parsed = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncLoopError(f"invalid items file: {source} ({exc})") from exc

    if not isinstance(parsed, list):
        raise SyncLoopError("items file must be a JSON array")

    rows: list[dict[str, Any]] = []
    for idx, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise SyncLoopError(f"items[{idx}] must be object")
        title = str(item.get("title", "")).strip()
        if not title:
            raise SyncLoopError(f"items[{idx}].title is required")
        rows.append(
            {
                "title": title,
                "summary": str(item.get("summary", "")).strip(),
                "files": [str(x).strip() for x in item.get("files", []) if str(x).strip()],
                "tags": [str(x).strip() for x in item.get("tags", []) if str(x).strip()],
                "category": str(item.get("category", "")).strip(),
                "note": str(item.get("note", "")).strip(),
            }
        )
    return rows


def _parse_git_status_line(line: str) -> tuple[str, str] | None:
    raw = str(line or "").rstrip("\n")
    if not raw:
        return None
    if len(raw) < 4:
        return None
    status = raw[:2]
    path_part = raw[3:].strip()
    if not path_part:
        return None
    if " -> " in path_part:
        path_part = path_part.split(" -> ", 1)[1].strip()
    if not path_part:
        return None
    return status.strip() or "??", path_part.replace("\\", "/")


def _collect_git_changes(*, max_files: int = 60) -> list[tuple[str, str]]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise SyncLoopError(f"git status failed: {exc}") from exc
    if proc.returncode != 0:
        raise SyncLoopError(f"git status failed: {proc.stderr.strip() or proc.stdout.strip()}")

    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for line in proc.stdout.splitlines():
        parsed = _parse_git_status_line(line)
        if parsed is None:
            continue
        status, path = parsed
        if path in seen:
            continue
        seen.add(path)
        rows.append((status, path))
        if len(rows) >= max(1, int(max_files)):
            break
    return rows


def _bucket_key(path: str) -> str:
    lowered = str(path or "").strip().lower()
    if lowered.startswith("apps/desktop/"):
        return "ui"
    if lowered.startswith("docs/") or lowered.startswith("spec/"):
        return "docs"
    for prefix in ("api/", "core/", "sophia_kernel/", "scripts/", "kernel/", "tests/"):
        if lowered.startswith(prefix):
            return prefix.split("/", 1)[0]
    top = lowered.split("/", 1)[0].strip()
    return top or "misc"


def _infer_category_from_bucket(bucket: str) -> str:
    key = str(bucket or "").strip().lower()
    if key in {"api", "core", "sophia_kernel", "kernel", "scripts", "tests"}:
        return "SYSTEM_CHANGE"
    if key == "ui":
        return "UI_CHANGE"
    if key == "docs":
        return "DOC_CHANGE"
    return "CHORE"


def _build_items_from_git(
    *,
    changes: list[tuple[str, str]],
    intent: str,
    max_items: int = 8,
    tracked_only: bool = True,
) -> list[dict[str, Any]]:
    groups: dict[str, list[tuple[str, str]]] = {}
    for status, path in changes:
        key = _bucket_key(path)
        groups.setdefault(key, []).append((status, path))

    rows: list[dict[str, Any]] = []
    for key, files in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0])):
        normalized_files = [path for _status, path in files if path]
        if not normalized_files:
            continue
        sample = ", ".join(normalized_files[:3])
        category = _infer_category_from_bucket(key)
        if tracked_only and category not in TRACKED_CATEGORIES:
            continue
        title = f"{key} changes ({len(normalized_files)})"
        summary = f"{intent.strip()} · {sample}" if intent.strip() else sample
        tags = ["git-auto", f"bucket:{key}", f"category:{category.lower()}"]
        rows.append(
            {
                "title": title,
                "summary": summary,
                "files": normalized_files[:15],
                "tags": tags,
                "category": category,
                "note": "from_git",
            }
        )
        if len(rows) >= max(1, int(max_items)):
            break
    return rows


def _post_json(base_url: str, path: str, payload: dict[str, Any], timeout: float = 10.0) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            parsed = json.loads(raw) if raw else {}
            if not isinstance(parsed, dict):
                raise SyncLoopError(f"invalid response body from {path}")
            parsed["_http_status"] = int(getattr(response, "status", 200) or 200)
            return parsed
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        detail: Any
        try:
            detail = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            detail = raw
        raise SyncLoopError(f"http {exc.code} {path}: {detail}") from exc
    except error.URLError as exc:
        raise SyncLoopError(f"network error {path}: {exc}") from exc


RequestFn = Callable[[str, str, dict[str, Any]], dict[str, Any]]
GetFn = Callable[[str, str], dict[str, Any]]


def _get_json(base_url: str, path: str, timeout: float = 10.0) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    req = request.Request(url, method="GET")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            parsed = json.loads(raw) if raw else {}
            if not isinstance(parsed, dict):
                raise SyncLoopError(f"invalid response body from {path}")
            parsed["_http_status"] = int(getattr(response, "status", 200) or 200)
            return parsed
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        detail: Any
        try:
            detail = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            detail = raw
        raise SyncLoopError(f"http {exc.code} {path}: {detail}") from exc
    except error.URLError as exc:
        raise SyncLoopError(f"network error {path}: {exc}") from exc


def _discover_openapi_paths(*, base_url: str, getter: GetFn) -> set[str]:
    try:
        openapi = getter(base_url, "/openapi.json")
    except SyncLoopError:
        return set()
    raw = openapi.get("paths", {})
    if not isinstance(raw, dict):
        return set()
    return {str(path) for path in raw.keys() if str(path).strip()}


def _run_status_sync(base_url: str, project: str, sender: RequestFn, export_canopy: bool) -> dict[str, Any]:
    query = "true" if bool(export_canopy) else "false"
    result = sender(
        base_url,
        f"/forest/projects/{project}/status/sync?view=focus&export_canopy={query}",
        {},
    )
    if "recorded" not in result:
        result["recorded"] = 1 if str(result.get("status", "")).strip().lower() == "ok" else 0
    if "skipped" not in result:
        result["skipped"] = 0
    if "skipped_items" not in result:
        result["skipped_items"] = []
    return result


def _extract_progress_roadmap_path(result: dict[str, Any]) -> str:
    steps = result.get("steps") if isinstance(result.get("steps"), dict) else {}
    for key in ("reconcile", "progress", "commit"):
        row = steps.get(key) if isinstance(steps.get(key), dict) else {}
        path = str(row.get("progress_roadmap_path", "")).strip()
        if path:
            return path
    return ""


def _append_sync_roadmap_summary(*, roadmap_path: str, intent: str, result: dict[str, Any]) -> dict[str, Any]:
    raw_path = str(roadmap_path or "").strip()
    if not raw_path:
        return {"appended": False, "reason": "no_path"}
    path = Path(raw_path)
    if not path.exists() or not path.is_file():
        return {"appended": False, "reason": "path_missing", "path": str(path)}

    sync_prefix = str(result.get("sync_prefix", "")).strip() or "unknown"
    mode = str(result.get("mode", "")).strip() or "unknown"
    legacy_variant = str(result.get("legacy_variant", "")).strip() or "-"
    recorded_total = int(result.get("recorded_total", 0) or 0)
    skipped_total = int(result.get("skipped_total", 0) or 0)
    now = datetime.now(UTC)
    stamp = now.isoformat().replace("+00:00", "Z")
    day_label = now.strftime("%Y-%m-%d")
    time_label = now.strftime("%H:%M:%S")
    intent_text = str(intent or "").strip() or "-"
    route_text = f"{sync_prefix} ({mode}/{legacy_variant})"
    summary_text = f"{time_label} · {intent_text} · {route_text} · {recorded_total}/{skipped_total}"

    try:
        existing_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {"appended": False, "reason": "read_failed", "path": str(path), "error": str(exc)}

    day_heading = f"### Sync Log {day_label}"
    lines = [""]
    if day_heading not in existing_text:
        lines.extend([day_heading, ""])
    lines.extend(
        [
            "<details>",
            f"<summary>{summary_text}</summary>",
            "",
            f"- at: {stamp}",
            f"- intent: {intent_text}",
            f"- route: {route_text}",
            f"- recorded/skipped: {recorded_total}/{skipped_total}",
            "",
            "</details>",
        ]
    )
    try:
        with path.open("a", encoding="utf-8") as file:
            file.write("\n".join(lines) + "\n")
    except OSError as exc:
        return {"appended": False, "reason": "write_failed", "path": str(path), "error": str(exc)}
    return {"appended": True, "path": str(path)}


def run_sync_loop(
    *,
    base_url: str,
    project: str,
    intent: str,
    mission_id: str = "",
    items: list[dict[str, Any]] | None = None,
    progress_note: str = "",
    commit: bool = False,
    tests_passed: bool = False,
    l2_passed: bool = False,
    proof: list[str] | None = None,
    failure_reason: str = "",
    final_summary: str = "",
    force_record: bool = False,
    skip_progress: bool = False,
    skip_reconcile: bool = False,
    override_token: str = "",
    sync_prefix: str = "auto",
    request_fn: RequestFn | None = None,
    get_fn: GetFn | None = None,
) -> dict[str, Any]:
    sender: RequestFn = request_fn or _post_json
    getter: GetFn = get_fn or _get_json
    mission_id = mission_id.strip()
    rows = list(items or [])
    proof_rows = [str(row).strip() for row in (proof or []) if str(row).strip()]
    raw_prefix = str(sync_prefix or "auto").strip().lower()
    candidate_prefixes = ["/sync", "/api/sync"] if raw_prefix in {"", "auto"} else ["/" + raw_prefix.strip("/")]
    prefix = ""
    legacy_variant = ""
    has_roadmap_record = False
    has_status_sync = False

    handshake_payload: dict[str, Any] = {"project_name": project, "intent": intent}
    if override_token.strip():
        handshake_payload["override_token"] = override_token.strip()

    handshake: dict[str, Any] | None = None
    last_error: SyncLoopError | None = None
    attempted_404: list[str] = []
    legacy_mode = False
    for candidate in candidate_prefixes:
        try:
            handshake = sender(base_url, f"{candidate}/handshake/init", handshake_payload)
            prefix = candidate
            break
        except SyncLoopError as exc:
            last_error = exc
            # "auto" mode: if route is missing, try next prefix.
            if raw_prefix in {"", "auto"} and "http 404" in str(exc):
                attempted_404.append(candidate)
                continue
            raise
    if handshake is None:
        if raw_prefix in {"", "auto"} and attempted_404 and len(attempted_404) == len(candidate_prefixes):
            # Legacy fallback for servers without /sync routes.
            openapi_paths = _discover_openapi_paths(base_url=base_url, getter=getter)
            has_roadmap_sync = "/forest/projects/{project_name}/roadmap/sync" in openapi_paths
            has_roadmap_record = "/forest/projects/{project_name}/roadmap/record" in openapi_paths
            has_status_sync = "/forest/projects/{project_name}/status/sync" in openapi_paths

            if has_roadmap_sync:
                handshake = {
                    "status": "ok",
                    "handshake": {"allowed": True, "code": "LEGACY_ROADMAP_SYNC", "reason": "legacy roadmap sync mode"},
                    "legacy": True,
                }
                prefix = "legacy"
                legacy_mode = True
                legacy_variant = "roadmap"
            elif has_status_sync:
                handshake = {
                    "status": "ok",
                    "handshake": {"allowed": True, "code": "LEGACY_STATUS_SYNC", "reason": "legacy status sync mode"},
                    "legacy": True,
                }
                prefix = "legacy"
                legacy_mode = True
                legacy_variant = "status"
            else:
                tried = ", ".join(f"{item}/handshake/init" for item in attempted_404)
                raise SyncLoopError(f"sync routes not found on server ({tried})")
        if handshake is None:
            if last_error is not None:
                raise last_error
            raise SyncLoopError("sync handshake failed: no available prefix")

    if str(handshake.get("status", "")).strip().lower() != "ok":
        return {
            "status": "forbidden",
            "project": project,
            "reason": str(handshake.get("handshake", {}).get("reason", "handshake_forbidden")),
            "steps": {"handshake": handshake},
            "recorded_total": 0,
            "skipped_total": 0,
            "sync_prefix": prefix,
        }

    steps: dict[str, Any] = {"handshake": handshake}
    recorded_total = 0
    skipped_total = 0

    if not skip_progress:
        if legacy_mode:
            if legacy_variant == "roadmap":
                progress_payload = {"items": rows, "force_record": bool(force_record)}
                progress_result = sender(base_url, f"/forest/projects/{project}/roadmap/sync", progress_payload)
            else:
                progress_result = _run_status_sync(base_url, project, sender, export_canopy=False)
                progress_result["recorded"] = int(progress_result.get("recorded", 0) or 0) + (
                    len(rows) if rows else 0
                )
        else:
            progress_payload = {
                "project_name": project,
                "mission_id": mission_id,
                "progress_note": progress_note,
                "items": rows,
                "force_record": bool(force_record),
            }
            progress_result = sender(base_url, f"{prefix}/progress", progress_payload)
        steps["progress"] = progress_result
        recorded_total += int(progress_result.get("recorded", 0) or 0)
        skipped_total += int(progress_result.get("skipped", 0) or 0)

    if commit:
        if legacy_mode:
            if mission_id:
                if bool(tests_passed and l2_passed):
                    sender(base_url, f"/work/packages/{mission_id}/complete", {})
                else:
                    sender(
                        base_url,
                        f"/work/packages/{mission_id}/report",
                        {
                            "work_package_id": mission_id,
                            "status": "BLOCKED",
                            "signals": [],
                            "artifacts": [],
                            "notes": failure_reason or "legacy commit validation failed",
                        },
                    )
            if legacy_variant == "roadmap":
                commit_result = sender(
                    base_url,
                    f"/forest/projects/{project}/roadmap/sync",
                    {"items": rows, "force_record": bool(force_record)},
                )
            else:
                commit_result = _run_status_sync(base_url, project, sender, export_canopy=True)
            commit_result["commit_status"] = "DONE" if bool(tests_passed and l2_passed) else "BLOCKED"
        else:
            commit_payload = {
                "project_name": project,
                "mission_id": mission_id,
                "final_summary": final_summary,
                "items": rows,
                "force_record": bool(force_record),
                "validation": {
                    "tests_passed": bool(tests_passed),
                    "l2_passed": bool(l2_passed),
                    "proof": proof_rows,
                    "failure_reason": failure_reason,
                },
            }
            commit_result = sender(base_url, f"{prefix}/commit", commit_payload)
        steps["commit"] = commit_result
        recorded_total += int(commit_result.get("recorded", 0) or 0)
        skipped_total += int(commit_result.get("skipped", 0) or 0)

    if not skip_reconcile:
        if legacy_mode:
            if legacy_variant == "roadmap" and has_roadmap_record:
                reconcile_result = sender(base_url, f"/forest/projects/{project}/roadmap/record", {"note": "legacy_sync_reconcile"})
                reconcile_result["recorded"] = 1 if str(reconcile_result.get("status", "")).lower() == "ok" else 0
                reconcile_result.setdefault("skipped_items", [])
            elif has_status_sync:
                reconcile_result = _run_status_sync(base_url, project, sender, export_canopy=True)
            else:
                reconcile_result = {"status": "ok", "recorded": 0, "skipped_items": [], "mode": "noop"}
        else:
            reconcile_payload = {
                "project_name": project,
                "apply": True,
                "note": "sync_forest_loop",
            }
            reconcile_result = sender(base_url, f"{prefix}/reconcile", reconcile_payload)
        steps["reconcile"] = reconcile_result
        recorded_total += int(reconcile_result.get("recorded", 0) or 0)
        skipped_total += int(len(reconcile_result.get("skipped_items", []) or []))

    return {
        "status": "ok",
        "project": project,
        "recorded_total": recorded_total,
        "skipped_total": skipped_total,
        "sync_prefix": prefix,
        "mode": "legacy" if legacy_mode else "sync",
        "legacy_variant": legacy_variant if legacy_mode else "",
        "steps": steps,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Sophia Forest sync loop (handshake/progress/commit/reconcile).")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="sync API base url")
    parser.add_argument("--project", default="sophia", help="forest project name")
    parser.add_argument("--intent", required=True, help="handshake intent text")
    parser.add_argument("--mission-id", default="", help="work package id")
    parser.add_argument("--items-file", default="", help="JSON file path for sync items list")
    parser.add_argument("--progress-note", default="", help="optional progress note")
    parser.add_argument("--commit", action=argparse.BooleanOptionalAction, default=False, help="also run /sync/commit")
    parser.add_argument("--tests-passed", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--l2-passed", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--proof", action="append", default=[], help="validation proof (repeatable)")
    parser.add_argument("--failure-reason", default="", help="commit failure reason")
    parser.add_argument("--final-summary", default="", help="commit summary text")
    parser.add_argument("--force-record", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--skip-progress", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--skip-reconcile", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--override-token", default="", help="optional preflight override token")
    parser.add_argument(
        "--sync-prefix",
        default="auto",
        help="sync router prefix path (auto|/sync|/api/sync)",
    )
    parser.add_argument(
        "--from-git",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="auto-build sync items from local git changes",
    )
    parser.add_argument("--git-max-files", type=int, default=60, help="max changed files to scan from git")
    parser.add_argument("--git-max-items", type=int, default=8, help="max grouped sync items built from git")
    parser.add_argument(
        "--git-tracked-only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="keep only tracked categories(SYSTEM_CHANGE/PROBLEM_FIX/FEATURE_ADD) when building git items",
    )
    parser.add_argument(
        "--append-roadmap-summary",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="append short sync execution summary into progress_roadmap.md when path is available",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        items = _parse_items_file(str(args.items_file or "").strip())
        git_changes: list[tuple[str, str]] = []
        auto_items: list[dict[str, Any]] = []
        if bool(args.from_git):
            git_changes = _collect_git_changes(max_files=max(1, int(args.git_max_files)))
            auto_items = _build_items_from_git(
                changes=git_changes,
                intent=str(args.intent),
                max_items=max(1, int(args.git_max_items)),
                tracked_only=bool(args.git_tracked_only),
            )
            items = [*items, *auto_items]
        result = run_sync_loop(
            base_url=str(args.base_url),
            project=str(args.project),
            intent=str(args.intent),
            mission_id=str(args.mission_id),
            items=items,
            progress_note=str(args.progress_note),
            commit=bool(args.commit),
            tests_passed=bool(args.tests_passed),
            l2_passed=bool(args.l2_passed),
            proof=list(args.proof or []),
            failure_reason=str(args.failure_reason),
            final_summary=str(args.final_summary),
            force_record=bool(args.force_record),
            skip_progress=bool(args.skip_progress),
            skip_reconcile=bool(args.skip_reconcile),
            override_token=str(args.override_token),
            sync_prefix=str(args.sync_prefix),
        )
        if bool(args.append_roadmap_summary):
            roadmap_path = _extract_progress_roadmap_path(result)
            append_summary = _append_sync_roadmap_summary(
                roadmap_path=roadmap_path,
                intent=str(args.intent),
                result=result,
            )
            result["roadmap_summary"] = append_summary
        if bool(args.from_git):
            result["git"] = {
                "changed_files": len(git_changes),
                "auto_items": len(auto_items),
            }
    except SyncLoopError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
