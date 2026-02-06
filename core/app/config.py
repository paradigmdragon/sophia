import json
import os
from typing import Dict, Any

class ConfigLoader:
    def __init__(self, config_path: str = "sone/subtitle.asr.sone"):
        self.config_path = config_path
        self._config = {}

    def load(self) -> Dict[str, Any]:
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
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
