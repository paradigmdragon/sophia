import os
import glob
import json
from typing import List, Optional
from .models import Task
from app.common.utils import get_logger

logger = get_logger("TaskLoader")

class TaskLoader:
    def __init__(self, tasks_dir: str):
        self.tasks_dir = tasks_dir
        if not os.path.exists(tasks_dir):
            try:
                os.makedirs(tasks_dir, exist_ok=True)
            except OSError as e:
                logger.error(f"Failed to create tasks directory {tasks_dir}: {e}")

    def scan_queued(self) -> List[str]:
        """
        Scans for tasks with status 'queued'.
        Returns list of task file paths.
        """
        queued_tasks = []
        pattern = os.path.join(self.tasks_dir, "*.task.json")
        
        # Get all task files
        files = glob.glob(pattern)
        
        # Sort by mtime (FIFO roughly, timestamp in name preferred)
        files.sort(key=os.path.getmtime)
        
        for f in files:
            # Check if locked
            if os.path.exists(f + ".lock"):
                continue
                
            try:
                with open(f, 'r', encoding='utf-8') as tf:
                    data = json.load(tf)
                    # Quick check status without full validation if perf matters, 
                    # but full parsing is safer
                    if data.get("status") == "queued":
                        queued_tasks.append(f)
            except Exception as e:
                logger.warning(f"Failed to read task file {f}: {e}")
                
        return queued_tasks

    def load_task(self, file_path: str) -> Optional[Task]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return Task(**data)
        except Exception as e:
            logger.error(f"Failed to load task from {file_path}: {e}")
            return None
