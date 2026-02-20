from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import inspect as sa_inspect, text


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _to_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    dt = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _parse_payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        value = raw.strip()
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def _is_recent(value: Any, *, days: int) -> bool:
    dt = _parse_dt(value)
    if dt is None:
        return False
    return (_utc_now() - dt) <= timedelta(days=max(1, int(days)))


def build_bitmap_audit_snapshot(
    session,
    *,
    days: int = 30,
    limit: int = 20,
    reason_limit: int = 8,
) -> dict[str, Any]:
    base = {
        "window_days": int(days),
        "totals": {
            "candidate_total": 0,
            "status_counts": {"PENDING": 0, "ADOPTED": 0, "REJECTED": 0, "UNKNOWN": 0},
            "event_counts": {"PROPOSE": 0, "ADOPT": 0, "REJECT": 0, "BITMAP_INVALID": 0, "CONFLICT_MARK": 0, "EPIDORA_MARK": 0},
        },
        "candidate_transitions": [],
        "top_failure_reasons": [],
        "recent_failures": [],
    }

    bind = session.get_bind()
    if bind is None:
        return base

    try:
        inspector = sa_inspect(bind)
    except Exception:
        return base

    status_counts = base["totals"]["status_counts"]
    event_counts = base["totals"]["event_counts"]
    candidate_index: dict[str, dict[str, Any]] = {}
    transition_map: dict[str, dict[str, Any]] = {}
    reason_counts: dict[str, int] = {}
    recent_failures: list[dict[str, Any]] = []

    try:
        if inspector.has_table("candidates"):
            rows = session.execute(
                text(
                    """
                    SELECT candidate_id, episode_id, status, proposed_at
                    FROM candidates
                    ORDER BY proposed_at DESC
                    LIMIT 5000
                    """
                )
            ).fetchall()
            for row in rows:
                proposed_at = row[3]
                if not _is_recent(proposed_at, days=days):
                    continue
                candidate_id = str(row[0] or "").strip()
                if not candidate_id:
                    continue
                status = str(row[2] or "").strip().upper() or "UNKNOWN"
                base["totals"]["candidate_total"] = int(base["totals"]["candidate_total"]) + 1
                if status in status_counts:
                    status_counts[status] = int(status_counts.get(status, 0)) + 1
                else:
                    status_counts["UNKNOWN"] = int(status_counts.get("UNKNOWN", 0)) + 1
                candidate_index[candidate_id] = {
                    "episode_id": str(row[1] or "").strip(),
                    "current_status": status,
                    "proposed_at": _to_iso(_parse_dt(proposed_at)),
                }

        if inspector.has_table("events"):
            event_columns = {column["name"] for column in inspector.get_columns("events")}
            has_episode_col = "episode_id" in event_columns
            if has_episode_col:
                rows = session.execute(
                    text(
                        """
                        SELECT event_id, type, payload, at, episode_id
                        FROM events
                        WHERE type IN ('PROPOSE', 'ADOPT', 'REJECT', 'BITMAP_INVALID', 'CONFLICT_MARK', 'EPIDORA_MARK')
                        ORDER BY at DESC
                        LIMIT 5000
                        """
                    )
                ).fetchall()
            else:
                rows = session.execute(
                    text(
                        """
                        SELECT event_id, type, payload, at, NULL AS episode_id
                        FROM events
                        WHERE type IN ('PROPOSE', 'ADOPT', 'REJECT', 'BITMAP_INVALID', 'CONFLICT_MARK', 'EPIDORA_MARK')
                        ORDER BY at DESC
                        LIMIT 5000
                        """
                    )
                ).fetchall()
            for row in rows:
                when = _parse_dt(row[3])
                if when is None or (_utc_now() - when) > timedelta(days=max(1, int(days))):
                    continue
                event_type = str(row[1] or "").strip().upper()
                if event_type not in event_counts:
                    continue
                event_counts[event_type] = int(event_counts.get(event_type, 0)) + 1

                payload = _parse_payload(row[2])
                candidate_id = str(payload.get("candidate_id", "")).strip()
                episode_id = str(row[4] or "").strip()
                at_iso = _to_iso(when)

                if event_type in {"PROPOSE", "ADOPT", "REJECT", "BITMAP_INVALID"} and candidate_id:
                    item = transition_map.setdefault(
                        candidate_id,
                        {
                            "candidate_id": candidate_id,
                            "episode_id": episode_id,
                            "transition_count": 0,
                            "last_event_type": "",
                            "last_at": "",
                            "current_status": candidate_index.get(candidate_id, {}).get("current_status", "UNKNOWN"),
                        },
                    )
                    item["transition_count"] = int(item["transition_count"]) + 1
                    if not item["last_at"]:
                        item["last_event_type"] = event_type
                        item["last_at"] = at_iso

                reason = ""
                if event_type == "REJECT":
                    reason = str(payload.get("reason", "")).strip().upper() or "REJECTED"
                elif event_type == "BITMAP_INVALID":
                    reason = str(payload.get("reason", "")).strip().upper() or "INVALID_BITMAP"
                elif event_type == "CONFLICT_MARK":
                    reason = "CONFLICT_MARK"
                elif event_type == "EPIDORA_MARK":
                    reason = str(payload.get("name", "")).strip().upper() or "EPIDORA_MARK"

                if reason:
                    reason_counts[reason] = int(reason_counts.get(reason, 0)) + 1
                    recent_failures.append(
                        {
                            "event_type": event_type,
                            "candidate_id": candidate_id,
                            "episode_id": episode_id,
                            "reason": reason,
                            "at": at_iso,
                        }
                    )
    except Exception:
        return base

    transitions = sorted(
        transition_map.values(),
        key=lambda item: (-int(item.get("transition_count", 0)), str(item.get("last_at", "")), str(item.get("candidate_id", ""))),
    )
    top_reasons = [
        {"reason": reason, "count": int(count)}
        for reason, count in sorted(reason_counts.items(), key=lambda pair: (-int(pair[1]), pair[0]))[: max(1, int(reason_limit))]
    ]

    base["candidate_transitions"] = transitions[: max(1, int(limit))]
    base["top_failure_reasons"] = top_reasons
    base["recent_failures"] = recent_failures[: max(1, int(limit) * 2)]
    return base
