from __future__ import annotations

from typing import Any

from core.forest.canopy import build_canopy_data


def evaluate_focus_policy(
    *,
    session,
    project_name: str,
    focus_mode: bool = True,
    focus_lock_level: str = "soft",
    wip_limit: int = 1,
    operation: str = "",
    target_mission_id: str | None = None,
) -> dict[str, Any]:
    normalized_level = str(focus_lock_level or "soft").strip().lower()
    if normalized_level not in {"soft", "hard"}:
        normalized_level = "soft"
    normalized_limit = max(1, int(wip_limit or 1))

    data = build_canopy_data(
        project_name=project_name,
        session=session,
        view="focus",
        focus_mode=bool(focus_mode),
        focus_lock_level=normalized_level,
        wip_limit=normalized_limit,
    )
    focus = data.get("focus") if isinstance(data.get("focus"), dict) else {}
    metrics = focus.get("metrics") if isinstance(focus.get("metrics"), dict) else {}
    active_mission_ids = (
        [str(row).strip() for row in focus.get("active_mission_ids", []) if str(row).strip()]
        if isinstance(focus.get("active_mission_ids"), list)
        else []
    )
    active_count = int(metrics.get("wip_active_count", 0) or 0)
    op = str(operation or "").strip().lower()
    target_id = str(target_mission_id or "").strip()

    blocked = False
    reason = ""
    if bool(focus_mode):
        if normalized_level == "hard":
            if active_count > 0 and op in {"work.create_package", "forest.work.generate", "forest.idea.promote"}:
                blocked = True
                reason = f"HARD_LOCK_ACTIVE:{active_count}"
        else:
            if active_count >= normalized_limit and op in {
                "work.create_package",
                "forest.work.generate",
                "forest.idea.promote",
                "work.promote",
            }:
                # Soft lock still permits actions on the currently active mission itself.
                if not target_id or target_id not in active_mission_ids:
                    blocked = True
                    reason = f"WIP_LIMIT_REACHED:{active_count}/{normalized_limit}"

    return {
        "blocked": blocked,
        "reason": reason,
        "wip_active_count": active_count,
        "wip_limit": normalized_limit,
        "focus_lock_level": normalized_level,
        "current_mission_id": focus.get("current_mission_id"),
        "active_mission_ids": active_mission_ids,
        "next_action": focus.get("next_action"),
    }
