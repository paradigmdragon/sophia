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

if __name__ == "__main__":
    cli()
