import os
import json
import uuid
from datetime import datetime
from typing import Dict, Any

class ChatLogger:
    def __init__(self, log_dir: str = "logs/chat"):
        self.log_dir = os.path.join(os.path.dirname(__file__), "..", log_dir)
        os.makedirs(self.log_dir, exist_ok=True)

    def log_message(self, role: str, content: str) -> str:
        """
        Logs a message to the daily JSONL file and returns the message_id.
        """
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        log_file = os.path.join(self.log_dir, f"{date_str}.jsonl")
        
        message_id = f"m_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.utcnow().isoformat()
        
        record = {
            "message_id": message_id,
            "timestamp": timestamp,
            "role": role,
            "content": content
        }
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            
        return message_id

    def get_log_uri(self) -> str:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        return f"logs/chat/{date_str}.jsonl"
