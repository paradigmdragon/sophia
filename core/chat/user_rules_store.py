from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import inspect as sa_inspect, text

from core.memory.schema import MindWorkingLog, UserRule


_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣_:-]+")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _to_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    dt = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _rule_type_from_needs(needs_type: str) -> str:
    mapping = {
        "meaning": "term_meaning",
        "scope": "default_scope",
        "priority": "preference",
        "timeframe": "preference",
        "target": "routing",
    }
    return mapping.get(needs_type, "preference")


def _is_expired(rule: UserRule, now: datetime) -> bool:
    ttl_days = int(rule.ttl_days or 0)
    if ttl_days <= 0:
        return False
    base = rule.updated_at or rule.created_at
    if base is None:
        return False
    if base.tzinfo is None:
        base = base.replace(tzinfo=UTC)
    return now > base.astimezone(UTC) + timedelta(days=ttl_days)


def extract_keywords(text: str, *, limit: int = 8) -> list[str]:
    raw = (text or "").lower()
    tokens = []
    seen = set()
    for token in _TOKEN_RE.findall(raw):
        if len(token) < 2:
            continue
        if token in seen:
            continue
        seen.add(token)
        tokens.append(token)
        if len(tokens) >= limit:
            break
    return tokens


def match_user_rules(session, text: str, *, limit: int = 5) -> list[dict[str, Any]]:
    keywords = extract_keywords(text, limit=12)
    if not keywords:
        return []

    now = _utc_now()
    rows = (
        session.query(UserRule)
        .order_by(UserRule.pinned.desc(), UserRule.hit_count.desc(), UserRule.updated_at.desc(), UserRule.id.desc())
        .limit(200)
        .all()
    )

    matched: list[dict[str, Any]] = []
    text_lower = (text or "").lower()
    for row in rows:
        if _is_expired(row, now):
            continue
        key = str(row.key or "").strip().lower()
        if not key:
            continue
        if key not in text_lower and key not in keywords:
            continue
        matched.append(
            {
                "id": int(row.id),
                "key": str(row.key),
                "value": str(row.value),
                "type": str(row.type),
                "pinned": bool(row.pinned),
                "ttl_days": int(row.ttl_days or 0),
                "hit_count": int(row.hit_count or 0),
                "last_used_at": _to_iso(row.last_used_at),
            }
        )
        if len(matched) >= limit:
            break
    return matched


def upsert_user_rule(
    session,
    *,
    key: str,
    value: str,
    rule_type: str,
    ttl_days: int = 30,
    pinned: bool = False,
) -> UserRule:
    clean_key = str(key or "").strip().lower()
    clean_value = str(value or "").strip()
    clean_type = str(rule_type or "preference").strip().lower()
    if not clean_key:
        raise ValueError("user rule key is required")
    if not clean_value:
        raise ValueError("user rule value is required")

    now = _utc_now()
    row = (
        session.query(UserRule)
        .filter(UserRule.key == clean_key, UserRule.type == clean_type)
        .one_or_none()
    )

    if row is None:
        row = UserRule(
            key=clean_key,
            value=clean_value,
            type=clean_type,
            pinned=bool(pinned),
            ttl_days=max(0, int(ttl_days)),
            hit_count=1,
            last_used_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.flush()
        return row

    row.value = clean_value
    row.ttl_days = max(0, int(ttl_days))
    row.pinned = bool(row.pinned or pinned)
    row.hit_count = int(row.hit_count or 0) + 1
    row.last_used_at = now
    row.updated_at = now
    session.add(row)
    session.flush()
    return row


def _append_learning_log(session, *, key: str, rule_type: str) -> None:
    now = _utc_now()
    line = f"[{now.strftime('%H:%M')}] user rule learned: {rule_type}:{key}"[:80]
    session.add(
        MindWorkingLog(
            line=line,
            event_type="USER_RULE_LEARNED",
            item_id=None,
            delta_priority=0,
            created_at=now,
        )
    )
    session.flush()


def _record_bitmap_candidate(session, *, key: str, value: str, rule_type: str) -> None:
    bind = session.get_bind()
    if bind is None:
        return
    try:
        inspector = sa_inspect(bind)
        if not inspector.has_table("events"):
            return
        session.execute(
            text(
                """
                INSERT INTO events (event_id, episode_id, type, payload, at)
                VALUES (:event_id, NULL, :event_type, :payload, CURRENT_TIMESTAMP)
                """
            ),
            {
                "event_id": f"evt_{uuid4().hex}",
                "event_type": "USER_RULE_CANDIDATE",
                "payload": '{"key":"%s","value":"%s","type":"%s"}'
                % (
                    key.replace('"', "'"),
                    value.replace('"', "'"),
                    rule_type.replace('"', "'"),
                ),
            },
        )
    except Exception:
        return


def learn_from_clarify_response(
    session,
    *,
    clarify_meta: dict[str, Any],
    user_text: str,
) -> dict[str, Any] | None:
    content = str(user_text or "").strip()
    if not content:
        return None

    needs = clarify_meta.get("needs") if isinstance(clarify_meta, dict) else None
    needs_type = "meaning"
    options: list[str] = []
    if isinstance(needs, dict):
        needs_type = str(needs.get("type", "meaning") or "meaning")
        raw_options = needs.get("options")
        if isinstance(raw_options, list):
            options = [str(item).strip().lower() for item in raw_options if str(item).strip()]

    key = options[0] if options else needs_type
    rule_type = _rule_type_from_needs(needs_type)
    row = upsert_user_rule(
        session,
        key=key,
        value=content,
        rule_type=rule_type,
        ttl_days=30,
        pinned=False,
    )
    _append_learning_log(session, key=key, rule_type=rule_type)
    _record_bitmap_candidate(session, key=key, value=content, rule_type=rule_type)

    return {
        "id": int(row.id),
        "key": str(row.key),
        "value": str(row.value),
        "type": str(row.type),
        "hit_count": int(row.hit_count or 0),
    }
