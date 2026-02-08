import click
import sys
import os

# Ensure app can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.pipeline import Pipeline
from app.common.utils import get_logger

logger = get_logger("CLI")

@click.group()
def cli():
    """Sophia v0.1.2 - Desktop ASR Factory"""
    pass

@cli.command()
@click.option("--files", required=True, help="Comma-separated paths to input files")
@click.option("--outdir", required=True, help="Output directory")
@click.option("--config", required=False, help="Path to config file")
def transcribe(files, outdir, config):
    """Transcribe specified files."""
    try:
        # TODO: Load config from path if provided, else use default behavior
        # For now, Pipeline loads default config internally or we could pass config path
        # Assuming Pipeline is updated to handle config path injection if needed, 
        # but spec says just pass config path. 
        # In this step we just handle CLI args parsing.
        
        file_list = [f.strip() for f in files.split(",") if f.strip()]
        
        pipeline = Pipeline(output_dir=outdir, config_path=config)
        # If we need to inject config path into pipeline:
        # pipeline.load_config(config) 
        
        pipeline.run(file_list)
        
    except Exception as e:
        logger.error(f"Critical Error: {e}")
        sys.exit(1)

from app.task.loader import TaskLoader
from app.task.runner import TaskRunner
import time

@cli.command()
@click.option("--watch", is_flag=True, help="Watch for queued tasks continuously")
@click.option("--task", help="Run a specific task by ID (file path or name)")
@click.option("--workspace", default=None, help="Path to workspace root")
def run(watch, task, workspace):
    """Run tasks from the workspace."""
    # Resolve workspace path
    if workspace:
        workspace_path = os.path.abspath(workspace)
    else:
        # Default: Try to find 'workspace' in project root
        # cli.py is in core/app/cli.py -> project root is ../..
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
        workspace_path = os.path.join(project_root, "workspace")
        
        # Fallback to CWD/workspace if strictly needed, but monorepo structure is preferred
        if not os.path.exists(workspace_path):
            logger.warning(f"Workspace not found at {workspace_path}, falling back to CWD/workspace")
            workspace_path = os.path.abspath("workspace")

    tasks_dir = os.path.join(workspace_path, "tasks")
    
    loader = TaskLoader(tasks_dir)
    runner = TaskRunner(workspace_path)
    
    logger.info(f"Sophia Task Runner v0.1.3 starting")
    logger.info(f"Resolved Workspace: {workspace_path}")

    if task:
        # Run specific task
        # Check if argument is full path or just filename
        task_path = task
        if not os.path.exists(task_path):
            task_path = os.path.join(tasks_dir, task)
            if not task_path.endswith(".task.json"):
                task_path += ".task.json"
        
        if not os.path.exists(task_path):
            logger.error(f"Task file not found: {task}")
            sys.exit(1)
            
        runner.process_task(task_path)
        
    elif watch:
        logger.info("Watching for queued tasks...")
        try:
            while True:
                queued = loader.scan_queued()
                for task_file in queued:
                    runner.process_task(task_file)
                
                if not queued:
                    time.sleep(1) # Poll interval
        except KeyboardInterrupt:
            logger.info("Stopping watcher...")
    else:
        logger.warning("Please specify --watch or --task <id>")

@cli.command()
@click.argument("message")
def chat(message):
    """Send a chat message to Sophia."""
    try:
        from core.manager import EpisodeManager
        import json
        
        # Initialize Manager
        # Note: manifest_path defaults to relative path in manager.py which might need adjustment 
        # based on CWD. Manager uses __file__ so it should be fine.
        manager = EpisodeManager()
        
        # Process Input
        result = manager.process_input(message)
        
        # Output result as JSON
        print(json.dumps(result, ensure_ascii=False, default=str))
        
    except Exception as e:
        logger.error(f"Chat Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    cli()
