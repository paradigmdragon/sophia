import click
import sys
import os

# Ensure app can be imported
# Ensure app can be imported
# Dual-path injection to support both 'from app...' and 'from core...' styles legacy codebase
current_dir = os.path.dirname(__file__)
core_path = os.path.abspath(os.path.join(current_dir, '..'))
root_path = os.path.abspath(os.path.join(current_dir, '..', '..'))

if core_path not in sys.path:
    sys.path.insert(0, core_path)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from core.app.pipeline import Pipeline
from core.app.common.utils import get_logger

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

from core.app.task.loader import TaskLoader
from core.app.task.runner import TaskRunner
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

@cli.command()
@click.argument("video_path")
@click.option("--srt", required=False, help="Path to SRT file for analysis/remapping")
def rough_cut(video_path, srt):
    """
    Auto Rough-Cut v0.1 Pipeline.
    """
    try:
        from core.rough_cut import RoughCutEngine
        import json
        
        logger.info(f"Starting Rough-Cut for: {video_path}")
        
        engine = RoughCutEngine()
        
        # 1. Prepare Workspace & Metadata
        ctx = engine.analyzer.prepare_workspace(video_path)
        work_dir = ctx["work_dir"]
        logger.info(f"Workspace: {work_dir}")
        
        # 2. Analyze Candidates
        candidates = engine.analyzer.analyze_candidates(work_dir, srt_path=srt)
        logger.info(f"Candidates: {len(candidates)} found")
        
        # 3. Decision Simulation (v0.1: Default = Cut candidates, Keep others)
        # In real UI, user would modify decisions. Here we just accept defaults.
        # But wait, logic says "Default Action" in candidate. 
        # So "descisions" list should be empty if we accept defaults?
        # Renderer logic: "For c in candidates: If user explicitly kept it... else CUT"
        # So passing empty decisions means "Do what candidates say" -> Cut all candidates.
        decisions = [] 
        
        # 4. Calculate Stable Keep Intervals
        duration_ms = ctx["meta"]["duration_ms"]
        keep_intervals = engine.renderer.calculate_keep_intervals(duration_ms, candidates, decisions)
        logger.info(f"Keep Intervals: {len(keep_intervals)} segments")
        
        # 5. Render
        engine.renderer.render(work_dir, keep_intervals, ctx["meta"])
        
        # 6. Remap SRT if provided
        if srt:
            engine.renderer.remap_srt(srt, keep_intervals, os.path.join(work_dir, "output_roughcut.srt"))
            
        logger.info("Rough-Cut Pipeline Completed Successfully.")
        print(json.dumps({"status": "success", "work_dir": work_dir}, ensure_ascii=False))
        
    except Exception as e:
        logger.error(f"Rough-Cut Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    cli()
