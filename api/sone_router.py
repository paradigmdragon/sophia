from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.config import settings
from core.engine.scheduler import get_scheduler

router = APIRouter(prefix="/sone", tags=["sone"])
_scheduler = get_scheduler(settings.db_path, poll_interval_seconds=5)


class RetryConfig(BaseModel):
    count: int = Field(default=0, ge=0, le=5)
    delay: int = Field(default=0, ge=0, le=3600)


class ScheduleConfig(BaseModel):
    type: Literal["immediate", "cron", "event"] = "immediate"
    value: str = ""


class RegisterCommandRequest(BaseModel):
    command_id: str | None = None
    name: str = Field(min_length=1, max_length=255)
    type: Literal["shell", "python", "http", "workflow"]
    priority: str = Field(default="P3", min_length=2, max_length=8)
    payload: dict[str, Any]
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    dependencies: list[str] = Field(default_factory=list)
    timeout: int = Field(default=30, ge=1, le=3600)
    retry: RetryConfig = Field(default_factory=RetryConfig)


@router.post("/commands")
def register_command(req: RegisterCommandRequest) -> dict[str, Any]:
    command = req.model_dump()
    return _scheduler.register_command(command)


@router.get("/commands")
def list_commands() -> list[dict[str, Any]]:
    return _scheduler.list_active_commands()

