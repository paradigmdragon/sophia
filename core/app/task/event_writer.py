import os
import json
from datetime import datetime
from .models import Event
from app.common.utils import get_logger

logger = get_logger("EventWriter")

class EventWriter:
    def __init__(self, events_dir: str):
        self.events_dir = events_dir
        if not os.path.exists(events_dir):
            os.makedirs(events_dir, exist_ok=True)
            
    def _get_current_log_file(self) -> str:
        # Rotate daily: 2026-02-06_events.jsonl
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        return os.path.join(self.events_dir, f"{date_str}_events.jsonl")

    def write(self, event: Event):
        try:
            file_path = self._get_current_log_file()
            # Append line (NDJSON)
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")
        except Exception as e:
            logger.error(f"Failed to write event: {e}")

    def emit(self, run_id: str, task_id: str, type: str, payload: dict):
        event = Event(
            run_id=run_id,
            task_id=task_id,
            type=type,
            payload=payload
        )
        self.write(event)
