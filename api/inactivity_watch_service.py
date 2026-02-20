from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4

from api.ledger_events import write_lifecycle_event
from api.sophia_notes import append_system_note
from core.memory.schema import ChatTimelineMessage, WatcherRun, create_session_factory
from sophia_kernel.modules.inactivity_watcher import EVENT_TYPE, run_inactivity_check
from sophia_kernel.modules.mind_diary import ingest_trigger_event, maybe_build_daily_diary

RULE_ID = "INACTIVITY_7D"
DEFAULT_USER_ID = "default"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _to_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    dt = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass
class InactivityWatcherConfig:
    enabled: bool = True
    threshold_days: int = 7
    cooldown_days: int = 3
    daily_limit: int = 1
    user_id: str = DEFAULT_USER_ID


class InactivityWatcherService:
    def __init__(self, *, db_path: str, config: InactivityWatcherConfig):
        self.config = config
        self.session_factory = create_session_factory(db_path=db_path)
        self._lock = Lock()

    def _dedup_key(self, *, window_start_date: str, template_id: str) -> str:
        return f"{self.config.user_id}:{RULE_ID}:{window_start_date}:{template_id}"

    def _daily_trigger_count(self, session, *, day: str) -> int:
        rows = (
            session.query(WatcherRun)
            .filter(
                WatcherRun.rule_id == RULE_ID,
                WatcherRun.user_id == self.config.user_id,
                WatcherRun.triggered.is_(True),
                WatcherRun.window_start_date == day,
            )
            .count()
        )
        return int(rows or 0)

    def _insert_watcher_run(
        self,
        session,
        *,
        dedup_key: str,
        window_start_date: str,
        template_id: str,
        triggered: bool,
        reason: str,
        result: dict[str, Any],
    ) -> None:
        row = WatcherRun(
            rule_id=RULE_ID,
            user_id=self.config.user_id,
            window_start_date=window_start_date,
            template_id=template_id,
            dedup_key=dedup_key,
            triggered=triggered,
            reason=reason,
            result=result,
            created_at=_utc_now(),
        )
        session.add(row)

    def run_once(self) -> dict[str, Any]:
        if not self.config.enabled:
            return {
                "ran": False,
                "triggered": False,
                "reason": "watcher_disabled",
                "next_eligible_at": "",
                "effects": {
                    "mind_items_created": 0,
                    "notes_appended": 0,
                    "messages_inserted": 0,
                    "ledger_events": [],
                },
            }

        if not self._lock.acquire(blocking=False):
            return {
                "ran": False,
                "triggered": False,
                "reason": "reentrant_skip",
                "next_eligible_at": "",
                "effects": {
                    "mind_items_created": 0,
                    "notes_appended": 0,
                    "messages_inserted": 0,
                    "ledger_events": [],
                },
            }

        ledger_events: list[str] = []
        effects = {
            "mind_items_created": 0,
            "notes_appended": 0,
            "messages_inserted": 0,
            "ledger_events": ledger_events,
        }
        try:
            now = _utc_now()
            eval_result = run_inactivity_check(
                session_factory=self.session_factory,
                now=now,
                threshold_days=self.config.threshold_days,
                cooldown_days=self.config.cooldown_days,
            )
            reason = str(eval_result.get("reason", "evaluated"))
            next_eligible_at = str(eval_result.get("next_eligible_at", ""))

            write_lifecycle_event(
                "INACTIVITY_CHECKED",
                {
                    "rule_id": RULE_ID,
                    "user_id": self.config.user_id,
                    "triggered": bool(eval_result.get("triggered", False)),
                    "reason": reason,
                    "next_eligible_at": next_eligible_at,
                    "days_inactive": eval_result.get("days_inactive"),
                },
                skill_id="watcher.inactivity",
            )
            ledger_events.append("INACTIVITY_CHECKED")

            if not bool(eval_result.get("triggered", False)):
                if reason == "cooldown_active":
                    write_lifecycle_event(
                        "INACTIVITY_SKIPPED_COOLDOWN",
                        {
                            "rule_id": RULE_ID,
                            "user_id": self.config.user_id,
                            "next_eligible_at": next_eligible_at,
                        },
                        skill_id="watcher.inactivity",
                    )
                    ledger_events.append("INACTIVITY_SKIPPED_COOLDOWN")
                return {
                    "ran": True,
                    "triggered": False,
                    "reason": reason,
                    "next_eligible_at": next_eligible_at,
                    "effects": effects,
                }

            question = eval_result.get("question", {})
            template_id = str(question.get("template_id", "C"))
            last_activity_at = str(eval_result.get("last_activity_at", ""))
            window_start_date = (last_activity_at[:10] if len(last_activity_at) >= 10 else now.date().isoformat())
            dedup_key = self._dedup_key(window_start_date=window_start_date, template_id=template_id)

            session = self.session_factory()
            try:
                existing = session.query(WatcherRun).filter(WatcherRun.dedup_key == dedup_key).one_or_none()
                if existing is not None:
                    result = {
                        "ran": True,
                        "triggered": False,
                        "reason": "dedup_hit",
                        "next_eligible_at": next_eligible_at,
                        "effects": effects,
                    }
                    write_lifecycle_event(
                        "INACTIVITY_SKIPPED_DEDUP",
                        {
                            "rule_id": RULE_ID,
                            "user_id": self.config.user_id,
                            "dedup_key": dedup_key,
                            "template_id": template_id,
                        },
                        skill_id="watcher.inactivity",
                    )
                    ledger_events.append("INACTIVITY_SKIPPED_DEDUP")
                    self._insert_watcher_run(
                        session,
                        dedup_key=f"{dedup_key}:skip:{uuid4().hex[:8]}",
                        window_start_date=now.date().isoformat(),
                        template_id=template_id,
                        triggered=False,
                        reason="dedup_hit",
                        result=result,
                    )
                    session.commit()
                    return result

                daily_count = self._daily_trigger_count(session, day=now.date().isoformat())
                if daily_count >= max(1, int(self.config.daily_limit)):
                    result = {
                        "ran": True,
                        "triggered": False,
                        "reason": "daily_rate_limited",
                        "next_eligible_at": next_eligible_at,
                        "effects": effects,
                    }
                    write_lifecycle_event(
                        "INACTIVITY_SKIPPED_DEDUP",
                        {
                            "rule_id": RULE_ID,
                            "user_id": self.config.user_id,
                            "dedup_key": f"daily_limit:{now.date().isoformat()}",
                            "template_id": template_id,
                            "reason": "daily_rate_limited",
                        },
                        skill_id="watcher.inactivity",
                    )
                    ledger_events.append("INACTIVITY_SKIPPED_DEDUP")
                    self._insert_watcher_run(
                        session,
                        dedup_key=f"{dedup_key}:daily:{uuid4().hex[:8]}",
                        window_start_date=now.date().isoformat(),
                        template_id=template_id,
                        triggered=False,
                        reason="daily_rate_limited",
                        result=result,
                    )
                    session.commit()
                    return result

                inactivity_days = float(eval_result.get("days_inactive", 0.0))
                question_text = str(question.get("question_text", "")).strip()
                cluster_id = str(question.get("cluster_id", "")).strip()

                # 1) Mind item projection
                mind_items = ingest_trigger_event(
                    session,
                    event_type=EVENT_TYPE,
                    payload={
                        "cluster_id": cluster_id,
                        "risk_score": 0.7,
                        "days_inactive": inactivity_days,
                        "template_id": template_id,
                    },
                )
                effects["mind_items_created"] = len(mind_items)

                # 2) Sophia note append
                note_result = append_system_note(
                    db=session,
                    note_type="SOPHIA_ACTIVITY_OBSERVATION",
                    source_events=[EVENT_TYPE],
                    summary=f"무활동 {inactivity_days:.1f}일 감지로 질문 1회를 생성했습니다.",
                    body_markdown="\n".join(
                        [
                            f"- inactivity_days: {inactivity_days:.1f}",
                            f"- reason_detected: {','.join(eval_result.get('note', {}).get('reason_detected', []))}",
                            f"- question_generated: {question_text}",
                            f"- next_cooldown_at: {next_eligible_at}",
                        ]
                    ),
                    status="ACTIVE",
                    actionables=[{"type": "answer_inactivity_question", "cluster_id": cluster_id}],
                    linked_cluster_id=cluster_id or None,
                    risk_score=0.7,
                    badge="QUESTION_READY",
                    dedup_key=f"inactivity:{now.date().isoformat()}:{template_id}",
                )
                if note_result.get("created", False):
                    effects["notes_appended"] = 1

                # 3) System question message insert
                message = ChatTimelineMessage(
                    id=f"msg_{uuid4().hex}",
                    role="sophia",
                    content=question_text,
                    context_tag="question-queue",
                    importance=0.82,
                    emotion_signal=None,
                    linked_cluster=cluster_id or None,
                    linked_node=None,
                    status="pending",
                    created_at=now,
                )
                session.add(message)
                effects["messages_inserted"] = 1

                # 4) Watcher run row
                result = {
                    "ran": True,
                    "triggered": True,
                    "reason": "inactivity_triggered",
                    "next_eligible_at": next_eligible_at,
                    "effects": effects,
                }
                self._insert_watcher_run(
                    session,
                    dedup_key=dedup_key,
                    window_start_date=window_start_date,
                    template_id=template_id,
                    triggered=True,
                    reason="triggered",
                    result=result,
                )

                # optional daily diary projection
                diary_payload = maybe_build_daily_diary(session)
                if diary_payload is not None:
                    append_system_note(
                        db=session,
                        note_type=str(diary_payload["note_type"]),
                        source_events=list(diary_payload["source_events"]),
                        summary=str(diary_payload["summary"]),
                        body_markdown=str(diary_payload["body_markdown"]),
                        status=str(diary_payload["status"]),
                        actionables=list(diary_payload["actionables"]),
                        badge=str(diary_payload["badge"]),
                        dedup_key=str(diary_payload["dedup_key"]),
                    )

                session.commit()

            finally:
                session.close()

            write_lifecycle_event(
                "INACTIVITY_TRIGGERED",
                {
                    "rule_id": RULE_ID,
                    "user_id": self.config.user_id,
                    "days_inactive": eval_result.get("days_inactive"),
                    "template_id": template_id,
                    "dedup_key": dedup_key,
                    "next_eligible_at": next_eligible_at,
                },
                skill_id="watcher.inactivity",
            )
            ledger_events.append("INACTIVITY_TRIGGERED")

            return {
                "ran": True,
                "triggered": True,
                "reason": "inactivity_triggered",
                "next_eligible_at": next_eligible_at,
                "effects": effects,
            }

        except Exception as exc:
            write_lifecycle_event(
                "INACTIVITY_CHECKED",
                {
                    "rule_id": RULE_ID,
                    "user_id": self.config.user_id,
                    "triggered": False,
                    "reason": f"error:{type(exc).__name__}",
                    "error": str(exc),
                },
                skill_id="watcher.inactivity",
            )
            return {
                "ran": True,
                "triggered": False,
                "reason": f"error:{type(exc).__name__}",
                "next_eligible_at": "",
                "effects": effects,
            }
        finally:
            self._lock.release()
