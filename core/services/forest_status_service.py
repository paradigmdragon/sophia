from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.forest.layout import ensure_project_layout, get_project_root, write_json

PROGRESS_SNAPSHOT_FILENAME = "progress_snapshot.json"
PROGRESS_ROADMAP_FILENAME = "progress_roadmap.md"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _min_work_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id", "")),
        "title": str(row.get("title", row.get("label", ""))),
        "status": str(row.get("status", "")),
        "module": str(row.get("module", "")),
        "module_label": str(row.get("module_label", row.get("module", ""))),
        "priority_score": int(row.get("priority_score", 0) or 0),
        "updated_at": str(row.get("updated_at", "")),
    }


def _build_next_actions(canopy_data: dict[str, Any]) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    used_titles: set[str] = set()

    risk = canopy_data.get("risk") if isinstance(canopy_data.get("risk"), dict) else {}
    risk_clusters = risk.get("clusters") if isinstance(risk.get("clusters"), list) else []
    for cluster in sorted(
        [row for row in risk_clusters if isinstance(row, dict)],
        key=lambda row: float(row.get("risk_score", 0.0) or 0.0),
        reverse=True,
    )[:3]:
        title = f"질문 클러스터 정리: {str(cluster.get('cluster_id', '')).strip()}"
        if not title.strip() or title in used_titles:
            continue
        used_titles.add(title)
        actions.append(
            {
                "priority": "P0",
                "title": title,
                "reason": f"risk {float(cluster.get('risk_score', 0.0) or 0.0):.2f}",
                "source": "question",
            }
        )

    roadmap = canopy_data.get("roadmap") if isinstance(canopy_data.get("roadmap"), dict) else {}
    pending = roadmap.get("pending") if isinstance(roadmap.get("pending"), list) else []
    in_progress = roadmap.get("in_progress") if isinstance(roadmap.get("in_progress"), list) else []

    for row in [item for item in pending if isinstance(item, dict)]:
        title = str(row.get("title", row.get("label", ""))).strip()
        if not title or title in used_titles:
            continue
        status = str(row.get("status", "")).upper()
        if status == "BLOCKED":
            priority = "P0"
            reason = "BLOCKED 상태 해소 필요"
        elif status == "FAILED":
            priority = "P0"
            reason = "FAILED 원인 정리 필요"
        else:
            priority = "P1"
            reason = "대기 작업 우선순위 결정"
        used_titles.add(title)
        actions.append({"priority": priority, "title": title, "reason": reason, "source": "work"})
        if len(actions) >= 8:
            break

    if len(actions) < 8:
        for row in [item for item in in_progress if isinstance(item, dict)]:
            title = str(row.get("title", row.get("label", ""))).strip()
            if not title or title in used_titles:
                continue
            used_titles.add(title)
            actions.append(
                {
                    "priority": "P1",
                    "title": title,
                    "reason": "진행 중 작업 완료 조건 점검",
                    "source": "work",
                }
            )
            if len(actions) >= 8:
                break

    sone = canopy_data.get("sone_summary") if isinstance(canopy_data.get("sone_summary"), dict) else {}
    bitmap = canopy_data.get("bitmap_health") if isinstance(canopy_data.get("bitmap_health"), dict) else {}
    missing_slot_count = int(sone.get("missing_slot_count", 0) or 0)
    if missing_slot_count > 0 and len(actions) < 8:
        title = f"SonE missing slot {missing_slot_count}건 정리"
        if title not in used_titles:
            actions.append(
                {
                    "priority": "P1",
                    "title": title,
                    "reason": "설계 누락 슬롯 보완 필요",
                    "source": "sone",
                }
            )

    if not actions:
        actions.append(
            {
                "priority": "P2",
                "title": "신규 명세 업로드 후 Grove 분석 실행",
                "reason": "현재 진행 데이터가 부족함",
                "source": "forest",
            }
        )
    return actions[:8]


def build_progress_snapshot(*, project_name: str, canopy_data: dict[str, Any]) -> dict[str, Any]:
    roadmap = canopy_data.get("roadmap") if isinstance(canopy_data.get("roadmap"), dict) else {}
    status_summary = (
        canopy_data.get("status_summary") if isinstance(canopy_data.get("status_summary"), dict) else {}
    )
    risk = canopy_data.get("risk") if isinstance(canopy_data.get("risk"), dict) else {}
    sone = canopy_data.get("sone_summary") if isinstance(canopy_data.get("sone_summary"), dict) else {}
    bitmap = canopy_data.get("bitmap_health") if isinstance(canopy_data.get("bitmap_health"), dict) else {}
    system_inventory = (
        canopy_data.get("system_inventory") if isinstance(canopy_data.get("system_inventory"), list) else []
    )
    events = canopy_data.get("recent_events") if isinstance(canopy_data.get("recent_events"), list) else []

    done_recent = [_min_work_row(row) for row in roadmap.get("done_recent", []) if isinstance(row, dict)][:8]
    in_progress = [_min_work_row(row) for row in roadmap.get("in_progress", []) if isinstance(row, dict)][:8]
    pending = [_min_work_row(row) for row in roadmap.get("pending", []) if isinstance(row, dict)][:8]

    recent_events = []
    for row in [item for item in events if isinstance(item, dict)][-20:]:
        recent_events.append(
            {
                "timestamp": str(row.get("timestamp", "")),
                "event_type": str(row.get("event_type", "")),
                "target": str(row.get("target", "")),
                "summary": str(row.get("summary", "")),
            }
        )

    system_status_counts: dict[str, int] = {"READY": 0, "IN_PROGRESS": 0, "DONE": 0, "BLOCKED": 0, "FAILED": 0}
    system_top: list[dict[str, Any]] = []
    for row in [item for item in system_inventory if isinstance(item, dict)]:
        status = str(row.get("status", "")).strip().upper()
        if status in system_status_counts:
            system_status_counts[status] = int(system_status_counts.get(status, 0)) + 1
        system_top.append(
            {
                "id": str(row.get("id", "")).strip(),
                "category": str(row.get("category", "")).strip(),
                "feature": str(row.get("feature", "")).strip(),
                "status": status or "READY",
                "progress_pct": int(row.get("progress_pct", 0) or 0),
                "risk_score": float(row.get("risk_score", 0.0) or 0.0),
                "updated_at": str(row.get("updated_at", "")).strip(),
            }
        )

    snapshot = {
        "version": "forest_progress_v0.1",
        "project": project_name,
        "synced_at": _utc_now_iso(),
        "canopy_generated_at": str(canopy_data.get("generated_at", "")),
        "summary": {
            "work_total": int(roadmap.get("total_work", 0) or 0),
            "remaining_work": int(roadmap.get("remaining_work", 0) or 0),
            "done_last_7d": int(roadmap.get("done_last_7d", 0) or 0),
            "eta_days": roadmap.get("eta_days"),
            "eta_hint": str(roadmap.get("eta_hint", "")),
            "status_counts": {
                "READY": int(status_summary.get("READY", 0) or 0),
                "IN_PROGRESS": int(status_summary.get("IN_PROGRESS", 0) or 0),
                "DONE": int(status_summary.get("DONE", 0) or 0),
                "BLOCKED": int(status_summary.get("BLOCKED", 0) or 0),
                "FAILED": int(status_summary.get("FAILED", 0) or 0),
                "UNVERIFIED": int(status_summary.get("UNVERIFIED", 0) or 0),
            },
            "risk": {
                "max_risk_score": float(risk.get("max_risk_score", 0.0) or 0.0),
                "unverified_count": int(risk.get("unverified_count", 0) or 0),
            },
            "sone": {
                "missing_slot_count": int(sone.get("missing_slot_count", 0) or 0),
                "impact_count": int(sone.get("impact_count", 0) or 0),
                "risk_cluster_count": int(sone.get("risk_cluster_count", 0) or 0),
                "source_doc": str(sone.get("source_doc", "")),
            },
            "bitmap": {
                "candidate_count_7d": int(bitmap.get("candidate_count_7d", 0) or 0),
                "pending_count": int(bitmap.get("pending_count", 0) or 0),
                "adoption_rate": float(bitmap.get("adoption_rate", 0.0) or 0.0),
                "invalid_count_7d": int(bitmap.get("invalid_count_7d", 0) or 0),
                "conflict_mark_count_7d": int(bitmap.get("conflict_mark_count_7d", 0) or 0),
                "duplicate_combined_groups": int(bitmap.get("duplicate_combined_groups", 0) or 0),
            },
            "systems": {
                "total": len(system_top),
                "status_counts": system_status_counts,
            },
        },
        "work": {
            "done_recent": done_recent,
            "in_progress": in_progress,
            "pending": pending,
        },
        "systems": {
            "rows": sorted(
                system_top,
                key=lambda row: (
                    -1 if str(row.get("status", "")).upper() in {"BLOCKED", "FAILED"} else 0,
                    -float(row.get("risk_score", 0.0) or 0.0),
                    int(row.get("progress_pct", 0) or 0),
                ),
            )[:12]
        },
        "next_actions": _build_next_actions(canopy_data),
        "recent_events": recent_events,
    }
    return snapshot


def build_progress_roadmap_markdown(snapshot: dict[str, Any]) -> str:
    summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), dict) else {}
    work = snapshot.get("work") if isinstance(snapshot.get("work"), dict) else {}
    systems_summary = summary.get("systems") if isinstance(summary.get("systems"), dict) else {}
    next_actions = snapshot.get("next_actions") if isinstance(snapshot.get("next_actions"), list) else []

    def _lines_for(rows: list[dict[str, Any]]) -> list[str]:
        lines: list[str] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            lines.append(
                "- {title} [{status}] ({module})".format(
                    title=str(row.get("title", "")).strip() or "-",
                    status=str(row.get("status", "")).strip() or "-",
                    module=str(row.get("module_label", row.get("module", ""))).strip() or "-",
                )
            )
        return lines or ["- (항목 없음)"]

    lines = [
        "# Sophia Forest 진행상태 로드맵",
        "",
        f"- project: {snapshot.get('project', '')}",
        f"- synced_at: {snapshot.get('synced_at', '')}",
        f"- canopy_generated_at: {snapshot.get('canopy_generated_at', '')}",
        "",
        "## 요약",
        f"- total_work: {int(summary.get('work_total', 0) or 0)}",
        f"- remaining_work: {int(summary.get('remaining_work', 0) or 0)}",
        f"- done_last_7d: {int(summary.get('done_last_7d', 0) or 0)}",
        f"- eta_days: {summary.get('eta_days', 'N/A')}",
        f"- eta_hint: {str(summary.get('eta_hint', '')).strip() or '-'}",
        f"- systems_total: {int(systems_summary.get('total', 0) or 0)}",
        f"- systems_status: {json.dumps(systems_summary.get('status_counts', {}), ensure_ascii=False)}",
        "",
        "## 완료(최근)",
        *_lines_for([row for row in work.get("done_recent", []) if isinstance(row, dict)]),
        "",
        "## 진행 중",
        *_lines_for([row for row in work.get("in_progress", []) if isinstance(row, dict)]),
        "",
        "## 대기/병목",
        *_lines_for([row for row in work.get("pending", []) if isinstance(row, dict)]),
        "",
        "## 다음 실행 항목",
    ]
    if next_actions:
        for row in next_actions:
            if not isinstance(row, dict):
                continue
            lines.append(
                "- [{priority}] {title} — {reason} ({source})".format(
                    priority=str(row.get("priority", "P2")),
                    title=str(row.get("title", "")).strip() or "-",
                    reason=str(row.get("reason", "")).strip() or "-",
                    source=str(row.get("source", "")).strip() or "-",
                )
            )
    else:
        lines.append("- (항목 없음)")
    lines.append("")
    return "\n".join(lines)


def sync_progress_snapshot(*, project_name: str, canopy_data: dict[str, Any]) -> dict[str, Any]:
    ensure_project_layout(project_name)
    root = get_project_root(project_name)
    status_dir = root / "status"
    snapshot_path = status_dir / PROGRESS_SNAPSHOT_FILENAME
    roadmap_path = status_dir / PROGRESS_ROADMAP_FILENAME

    snapshot = build_progress_snapshot(project_name=project_name, canopy_data=canopy_data)
    roadmap_markdown = build_progress_roadmap_markdown(snapshot)

    write_json(snapshot_path, snapshot)
    roadmap_path.write_text(roadmap_markdown, encoding="utf-8")

    return {
        "snapshot": snapshot,
        "snapshot_path": str(snapshot_path),
        "roadmap_path": str(roadmap_path),
    }


def load_progress_snapshot(*, project_name: str) -> dict[str, Any] | None:
    path = get_project_root(project_name) / "status" / PROGRESS_SNAPSHOT_FILENAME
    if not path.exists():
        return None
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None
