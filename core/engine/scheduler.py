from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import requests
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from core.memory.schema import SonECommand, create_session_factory

_CRON_EVERY_MINUTE = re.compile(r"^\*\s+\*\s+\*\s+\*\s+\*$")
_CRON_EVERY_N_MINUTES = re.compile(r"^\*/(?P<interval>\d+)\s+\*\s+\*\s+\*\s+\*$")
_SCHEDULERS: dict[str, "SoneScheduler"] = {}


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except Exception:
        return repr(value)


def _parse_cron_minutes(expr: str) -> int | None:
    text = (expr or "").strip()
    if _CRON_EVERY_MINUTE.match(text):
        return 1
    match = _CRON_EVERY_N_MINUTES.match(text)
    if not match:
        return None
    interval = int(match.group("interval"))
    return interval if interval > 0 else None


class SoneScheduler:
    def __init__(self, db_path: str = "sqlite:///sophia.db", poll_interval_seconds: int = 5):
        self.db_path = db_path
        self.poll_interval_seconds = max(1, int(poll_interval_seconds))
        self.session_factory = create_session_factory(db_path=db_path)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._periodic_jobs: dict[str, dict[str, Any]] = {}
        self._periodic_jobs_lock = threading.Lock()

    def _new_session(self) -> Session:
        return self.session_factory()

    def register_command(self, command: dict[str, Any]) -> dict[str, Any]:
        schedule = command.get("schedule") if isinstance(command.get("schedule"), dict) else {}
        retry = command.get("retry") if isinstance(command.get("retry"), dict) else {}
        schedule_type = str(schedule.get("type", "immediate"))
        schedule_value = str(schedule.get("value", "") or "")

        now = _utc_now()
        next_run_at = self._initial_next_run(schedule_type, schedule_value, now)
        command_id = str(command.get("command_id") or f"cmd_{uuid4().hex}")
        dependencies = command.get("dependencies")
        if not isinstance(dependencies, list):
            dependencies = []

        payload = command.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("command.payload must be an object")

        cmd_type = str(command.get("type", "")).strip()
        if cmd_type not in {"shell", "python", "http", "workflow"}:
            raise ValueError("command.type must be one of: shell, python, http, workflow")

        name = str(command.get("name", "")).strip()
        if not name:
            raise ValueError("command.name is required")

        timeout = int(command.get("timeout", 30) or 30)
        retry_count = int(retry.get("count", 0) or 0)
        retry_delay = int(retry.get("delay", 0) or 0)

        session = self._new_session()
        try:
            exists = (
                session.query(SonECommand)
                .filter(SonECommand.command_id == command_id)
                .one_or_none()
            )
            if exists:
                raise ValueError(f"command_id already exists: {command_id}")

            row = SonECommand(
                command_id=command_id,
                name=name,
                type=cmd_type,
                priority=str(command.get("priority", "P3")),
                payload=payload,
                schedule_type=schedule_type,
                schedule_value=schedule_value,
                dependencies=dependencies,
                timeout=timeout,
                retry_count=max(0, retry_count),
                retry_delay=max(0, retry_delay),
                active=True,
                next_run_at=next_run_at,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._serialize_command(row)
        finally:
            session.close()

    def list_active_commands(self) -> list[dict[str, Any]]:
        session = self._new_session()
        try:
            rows = (
                session.query(SonECommand)
                .filter(SonECommand.active.is_(True))
                .order_by(SonECommand.created_at.desc(), SonECommand.id.desc())
                .all()
            )
            return [self._serialize_command(row) for row in rows]
        finally:
            session.close()

    def run_due_once(self) -> dict[str, int]:
        now = _utc_now()
        session = self._new_session()
        executed = 0
        try:
            due_rows = (
                session.query(SonECommand)
                .filter(
                    SonECommand.active.is_(True),
                    SonECommand.next_run_at.is_not(None),
                    SonECommand.next_run_at <= now,
                )
                .order_by(SonECommand.next_run_at.asc(), SonECommand.id.asc())
                .all()
            )

            for row in due_rows:
                result = self._execute_with_retry(row)
                executed += 1
                self._finalize_command(session, row, result, now)
                self._log_execution(session, row, result, now)
                session.commit()
        finally:
            session.close()
        return {"executed": executed}

    def register_periodic_job(
        self,
        *,
        name: str,
        callback: Callable[[], Any],
        interval_seconds: int,
        startup_delay_seconds: int = 0,
    ) -> dict[str, Any]:
        job_name = str(name or "").strip()
        if not job_name:
            raise ValueError("periodic job name is required")
        if not callable(callback):
            raise TypeError("periodic job callback must be callable")

        interval = max(1, int(interval_seconds))
        startup_delay = max(0, int(startup_delay_seconds))
        now_mono = time.monotonic()
        next_run = now_mono + startup_delay

        with self._periodic_jobs_lock:
            self._periodic_jobs[job_name] = {
                "name": job_name,
                "callback": callback,
                "interval_seconds": interval,
                "startup_delay_seconds": startup_delay,
                "next_run_monotonic": next_run,
                "running": False,
            }

        return {
            "name": job_name,
            "interval_seconds": interval,
            "startup_delay_seconds": startup_delay,
        }

    def list_periodic_jobs(self) -> list[dict[str, Any]]:
        now_mono = time.monotonic()
        with self._periodic_jobs_lock:
            rows = []
            for job in self._periodic_jobs.values():
                rows.append(
                    {
                        "name": str(job["name"]),
                        "interval_seconds": int(job["interval_seconds"]),
                        "startup_delay_seconds": int(job["startup_delay_seconds"]),
                        "running": bool(job["running"]),
                        "seconds_until_next_run": max(0.0, float(job["next_run_monotonic"]) - now_mono),
                    }
                )
            return rows

    def run_periodic_once(self, *, now_monotonic: float | None = None) -> dict[str, Any]:
        now_mono = float(now_monotonic) if now_monotonic is not None else time.monotonic()
        run_jobs: list[dict[str, Any]] = []

        with self._periodic_jobs_lock:
            for job in self._periodic_jobs.values():
                if bool(job.get("running", False)):
                    continue
                if now_mono < float(job.get("next_run_monotonic", 0.0)):
                    continue
                job["running"] = True
                run_jobs.append(job)

        executed = 0
        failed = 0
        errors: list[dict[str, str]] = []
        for job in run_jobs:
            try:
                callback = job["callback"]
                callback()
                executed += 1
            except Exception as exc:
                failed += 1
                errors.append({"name": str(job.get("name", "")), "error": f"{type(exc).__name__}: {exc}"})
            finally:
                end_mono = float(now_monotonic) if now_monotonic is not None else time.monotonic()
                with self._periodic_jobs_lock:
                    current = self._periodic_jobs.get(str(job.get("name", "")))
                    if current is not None:
                        current["running"] = False
                        current["next_run_monotonic"] = end_mono + float(current["interval_seconds"])

        return {"executed": executed, "failed": failed, "errors": errors}

    def _execute_with_retry(self, row: SonECommand) -> dict[str, Any]:
        attempts = max(1, int(row.retry_count or 0) + 1)
        last_result: dict[str, Any] = {}
        for idx in range(attempts):
            attempt_no = idx + 1
            last_result = self._execute_once(row)
            last_result["attempt"] = attempt_no
            last_result["attempt_max"] = attempts
            if bool(last_result.get("ok", False)):
                return last_result
            if attempt_no < attempts and int(row.retry_delay or 0) > 0:
                time.sleep(int(row.retry_delay or 0))
        return last_result

    def _execute_once(self, row: SonECommand) -> dict[str, Any]:
        started = _utc_now()
        try:
            if row.type == "shell":
                result = self._execute_shell(row.payload, timeout=int(row.timeout))
            elif row.type == "python":
                result = self._execute_python(row.payload)
            elif row.type == "http":
                result = self._execute_http(row.payload, timeout=int(row.timeout))
            elif row.type == "workflow":
                result = self._execute_workflow(row.payload, timeout=int(row.timeout))
            else:
                raise ValueError(f"unsupported command type: {row.type}")
        except Exception as exc:
            finished = _utc_now()
            return {
                "ok": False,
                "error": {"type": type(exc).__name__, "message": str(exc)},
                "started_at": _to_iso(started),
                "finished_at": _to_iso(finished),
            }

        finished = _utc_now()
        result["started_at"] = _to_iso(started)
        result["finished_at"] = _to_iso(finished)
        return result

    def _execute_shell(self, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
        command = payload.get("command")
        if not isinstance(command, str) or not command.strip():
            raise ValueError("shell payload.command is required")
        args = payload.get("args") if isinstance(payload.get("args"), list) else []
        args = [str(arg) for arg in args]
        cwd = payload.get("cwd")
        if cwd is not None:
            cwd = str(cwd)
        env = payload.get("env") if isinstance(payload.get("env"), dict) else {}
        merged_env = dict(os.environ)
        for key, value in env.items():
            merged_env[str(key)] = str(value)

        proc = subprocess.run(
            [command, *args],
            capture_output=True,
            text=True,
            timeout=max(1, timeout),
            cwd=cwd,
            env=merged_env,
        )
        return {
            "ok": proc.returncode == 0,
            "return_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }

    def _resolve_python_callable(self, module_name: str, function_path: str):
        module = importlib.import_module(module_name)
        target: Any = module
        for name in function_path.split("."):
            if not name:
                continue
            if not hasattr(target, name):
                raise AttributeError(f"{function_path} not found on module {module_name}")
            target = getattr(target, name)
        if not callable(target):
            raise TypeError(f"{module_name}.{function_path} is not callable")
        return target

    def _execute_python(self, payload: dict[str, Any]) -> dict[str, Any]:
        module_name = payload.get("module")
        function_name = payload.get("function")
        if not isinstance(module_name, str) or not module_name.strip():
            raise ValueError("python payload.module is required")
        if not isinstance(function_name, str) or not function_name.strip():
            raise ValueError("python payload.function is required")

        args = payload.get("args") if isinstance(payload.get("args"), list) else []
        kwargs = payload.get("kwargs") if isinstance(payload.get("kwargs"), dict) else {}
        fn = self._resolve_python_callable(module_name, function_name)
        result = fn(*args, **kwargs)
        return {"ok": True, "result": _json_safe(result)}

    def _execute_http(self, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
        method = str(payload.get("method", "GET")).upper()
        url = payload.get("url")
        if not isinstance(url, str) or not url.strip():
            raise ValueError("http payload.url is required")
        headers = payload.get("headers") if isinstance(payload.get("headers"), dict) else {}
        body = payload.get("body")

        req_kwargs: dict[str, Any] = {"headers": headers, "timeout": max(1, timeout)}
        if isinstance(body, dict):
            req_kwargs["json"] = body
        elif body is not None:
            req_kwargs["data"] = str(body)

        response = requests.request(method=method, url=url, **req_kwargs)
        response_text = response.text
        if len(response_text) > 4000:
            response_text = response_text[:4000]
        return {
            "ok": 200 <= response.status_code < 400,
            "status_code": response.status_code,
            "response_text": response_text,
        }

    def _execute_workflow(self, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
        steps = payload.get("steps")
        if not isinstance(steps, list):
            raise ValueError("workflow payload.steps must be a list")
        step_results: list[dict[str, Any]] = []
        for step in steps:
            if not isinstance(step, dict):
                step_results.append({"ok": False, "error": "invalid step"})
                return {"ok": False, "steps": step_results}

            step_type = step.get("type")
            step_payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
            if step_type == "shell":
                result = self._execute_shell(step_payload, timeout=timeout)
            elif step_type == "python":
                result = self._execute_python(step_payload)
            elif step_type == "http":
                result = self._execute_http(step_payload, timeout=timeout)
            else:
                result = {"ok": False, "error": f"unsupported workflow step type: {step_type}"}

            step_results.append(result)
            if not bool(result.get("ok", False)):
                return {"ok": False, "steps": step_results}
        return {"ok": True, "steps": step_results}

    def _initial_next_run(self, schedule_type: str, schedule_value: str, now: datetime) -> datetime | None:
        if schedule_type == "immediate":
            return now
        if schedule_type == "cron":
            interval = _parse_cron_minutes(schedule_value)
            if interval is None:
                raise ValueError(f"unsupported cron expression: {schedule_value}")
            return now
        if schedule_type == "event":
            return None
        raise ValueError(f"unsupported schedule type: {schedule_type}")

    def _finalize_command(
        self,
        session: Session,
        row: SonECommand,
        result: dict[str, Any],
        now: datetime,
    ) -> None:
        ok = bool(result.get("ok", False))
        row.last_run_at = now
        row.last_status = "success" if ok else "failed"
        row.last_error = None if ok else json.dumps(result.get("error", {}), ensure_ascii=False)

        if row.schedule_type == "immediate":
            row.active = False
            row.next_run_at = None
        elif row.schedule_type == "cron":
            interval = _parse_cron_minutes(row.schedule_value)
            if interval is None:
                row.active = False
                row.next_run_at = None
                row.last_status = "failed"
                row.last_error = json.dumps(
                    {"type": "ValueError", "message": f"unsupported cron expression: {row.schedule_value}"},
                    ensure_ascii=False,
                )
            else:
                row.next_run_at = now + timedelta(minutes=interval)
        elif row.schedule_type == "event":
            row.next_run_at = None
        else:
            row.active = False
            row.next_run_at = None
            row.last_status = "failed"
            row.last_error = json.dumps(
                {"type": "ValueError", "message": f"unsupported schedule type: {row.schedule_type}"},
                ensure_ascii=False,
            )

        session.add(row)

    def _log_execution(
        self,
        session: Session,
        row: SonECommand,
        result: dict[str, Any],
        now: datetime,
    ) -> None:
        event_payload = {
            "command_id": row.command_id,
            "name": row.name,
            "type": row.type,
            "schedule_type": row.schedule_type,
            "ok": bool(result.get("ok", False)),
            "result": _json_safe(result),
        }

        # 1) JSONL task log
        date_str = now.date().isoformat()
        log_dir = Path("logs/tasks")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{date_str}.jsonl"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": _to_iso(now), **event_payload}, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

        # 2) Event table (best effort)
        try:
            from core.engine.schema import Event

            bind = session.get_bind()
            if bind is not None and sa_inspect(bind).has_table("events"):
                event = Event(
                    event_id=f"evt_{uuid4().hex}",
                    episode_id=None,
                    type="SONE_COMMAND_EXEC",
                    payload=event_payload,
                    at=now,
                )
                session.add(event)
        except Exception:
            # Keep scheduler non-fatal if Event table/model is unavailable.
            pass

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_due_once()
            except Exception:
                # scheduler loop should stay alive
                pass
            try:
                self.run_periodic_once()
            except Exception:
                # periodic loop should stay alive
                pass
            self._stop_event.wait(self.poll_interval_seconds)

    def start_background(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, name="sone-scheduler", daemon=True)
        self._thread.start()

    def stop_background(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=max(1, self.poll_interval_seconds + 1))

    def _serialize_command(self, row: SonECommand) -> dict[str, Any]:
        return {
            "id": row.id,
            "command_id": row.command_id,
            "name": row.name,
            "type": row.type,
            "priority": row.priority,
            "payload": row.payload,
            "schedule": {"type": row.schedule_type, "value": row.schedule_value},
            "dependencies": row.dependencies or [],
            "timeout": row.timeout,
            "retry": {"count": row.retry_count, "delay": row.retry_delay},
            "active": bool(row.active),
            "next_run_at": _to_iso(row.next_run_at),
            "last_run_at": _to_iso(row.last_run_at),
            "last_status": row.last_status,
            "last_error": row.last_error,
            "created_at": _to_iso(row.created_at),
            "updated_at": _to_iso(row.updated_at),
        }


def get_scheduler(db_path: str = "sqlite:///sophia.db", poll_interval_seconds: int = 5) -> SoneScheduler:
    key = f"{db_path}|{poll_interval_seconds}"
    scheduler = _SCHEDULERS.get(key)
    if scheduler is None:
        scheduler = SoneScheduler(db_path=db_path, poll_interval_seconds=poll_interval_seconds)
        _SCHEDULERS[key] = scheduler
    return scheduler
