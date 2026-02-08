import json
import os
from typing import Dict, Any

class ConfigLoader:
    def __init__(self, config_path: str = "sone/subtitle.asr.sone"):
        self.config_path = config_path
        self._config = {}
        
        # Resolve path
        if not os.path.exists(self.config_path):
            # Try project root (assuming we are in core/app/config.py)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
            possible_path = os.path.join(project_root, self.config_path)
            
            if os.path.exists(possible_path):
                self.config_path = possible_path

    def load(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            # Log CWD for debugging
            cwd = os.getcwd()
            raise FileNotFoundError(f"Config file not found: {self.config_path} (CWD: {cwd})")
        
        with open(self.config_path, "r", encoding="utf-8") as f:
            try:
                self._config = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in config file: {e}")
        
        return self._config

    @property
    def config(self) -> Dict[str, Any]:
        if not self._config:
            self.load()
        return self._config

def get_config() -> Dict[str, Any]:
    loader = ConfigLoader()
    return loader.load()
