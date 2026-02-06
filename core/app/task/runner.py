import os
import json
import time
import traceback
from typing import Optional
from .models import Task, TaskOutput
from .event_writer import EventWriter
from app.pipeline import Pipeline
from app.common.utils import get_logger

logger = get_logger("TaskRunner")

class TaskRunner:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        self.tasks_dir = os.path.join(workspace_dir, "tasks")
        self.events_dir = os.path.join(workspace_dir, "events")
        
        self.event_writer = EventWriter(self.events_dir)
        
    def process_task(self, task_file_path: str):
        """
        Atomic processing of a task file.
        1. Lock
        2. Set Running
        3. Execute
        4. Set Done/Failed
        5. Unlock
        """
        lock_file = task_file_path + ".lock"
        task_id = "unknown"
        run_id = "unknown"
        
        # 1. Acquire Lock
        if os.path.exists(lock_file):
            logger.info(f"Task {task_file_path} is currently locked. Skipping.")
            return

        try:
            # Create lock
            with open(lock_file, 'w') as f:
                f.write(str(time.time()))
                
            # 2. Read & Set Running
            with open(task_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            task = Task(**data)
            task_id = task.task_id
            run_id = task.run_id
            
            if task.status != "queued":
                logger.info(f"Task {task_id} is not queued ({task.status}). Skipping.")
                os.remove(lock_file)
                return

            logger.info(f"Starting Task: {task_id}")
            task.status = "running"
            self._save_task(task, task_file_path)
            
            # Emit Started
            self.event_writer.emit(run_id, task_id, "task.started", {
                "input": task.input.model_dump(),
                "pipeline": task.pipeline
            })
            
            # 3. Execute Pipeline
            # Construct Pipeline with config from Task
            # Note: Pipeline currently needs refactoring to match Spec v0.1 fully,
            # but we bridge it here.
            # Convert Task config snapshot to dict if needed by Pipeline
            
            # Determine processing paths
            # Input path is relative to workspace root usually, but spec says "workspace/inbox/..."
            # So if we run from project root, it works.
            # If we run from core/, we might need to adjust.
            # Let's assume absolute paths or CWD is project root.
            
            # Ensure output directories exist based on Task Output spec
            # Task Output schema in 0.1 is predefined paths.
            
            input_file = task.input.media
            if not os.path.exists(input_file):
                 # Try relative to workspace
                 possible_path = os.path.join(self.workspace_dir, "..", input_file) # input_file="workspace/inbox/..."
                 if os.path.exists(possible_path):
                     input_file = possible_path
            
            # Instantiate Pipeline
            # We assume Pipeline can take output_dir via init. 
            # But Task spec implies specific output files.
            # For v0.1 bridge, we trust Pipeline's internal logic for standard paths
            # OR we override it.
            # Current Pipeline writes to `outbox` = output_dir.
            # Spec says `outputs/subtitles/raw`, etc.
            # We should pass `workspace/outputs` as base output_dir to Pipeline.
            
            outputs_dir = os.path.join(self.workspace_dir, "outputs")
            
            # Temporary: Write config to temp file for Pipeline to load if it relies on file path
            # Or pass dict if supported. pipeline.py supports config_path str.
            # We will rely on default config for now or handle snapshot later.
            
            pipeline = Pipeline(output_dir=outputs_dir)
            
            # Run Single File
            # Pipeline.process_file expects a file path.
            # It currently emits events to stdout/listeners. 
            # We can capture them if we refactor, but for now we focus on Task status.
            
            pipeline.process_file(input_file)
            
            # 4. Set Done
            task.status = "done"
            
            # Update output paths in Task object (if pipeline generated standard names)
            # For now, hardcode based on assumption or read from Pipeline result if refactored.
            # We'll just mark done for v0.1
            
            self._save_task(task, task_file_path)
            
            self.event_writer.emit(run_id, task_id, "task.completed", {
                "duration_sec": 0 # TODO: calc duration
            })
            
        except Exception as e:
            logger.error(f"Task Failed: {e}")
            trace = traceback.format_exc()
            
            # Reload task to avoid stale overwrite? No, we hold lock.
            # Set Failed
            if 'task' in locals():
                task.status = "failed"
                task.error = {"message": str(e), "trace": trace}
                self._save_task(task, task_file_path)
                
                self.event_writer.emit(run_id, task_id, "task.failed", {
                    "error": str(e),
                    "trace": trace
                })
            
        finally:
            # 5. Unlock
            if os.path.exists(lock_file):
                os.remove(lock_file)

    def _save_task(self, task: Task, path: str):
        with open(path, 'w', encoding='utf-8') as f:
            # Pydantic v2: Use model_dump and json.dump for pretty printing
            json.dump(task.model_dump(mode='json'), f, indent=2, ensure_ascii=False)
