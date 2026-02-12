import os
import json
import uuid
from datetime import datetime
from typing import Dict, Any

class ChatLogger:
    def __init__(self, log_dir: str = "logs/chat"):
        self.log_dir = os.path.join(os.path.dirname(__file__), "..", log_dir)
        os.makedirs(self.log_dir, exist_ok=True)

    def log_message(self, role: str, content: str, **kwargs) -> str:
        """
        Logs a message to the daily JSONL file and returns the message_id.
        Supports extra metadata (e.g., epidora_coordinate for Shin process).
        """
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self.log_dir, f"{date_str}.jsonl")
        
        message_id = f"m_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now().isoformat()
        
        record = {
            "message_id": message_id,
            "timestamp": timestamp,
            "role": role,
            "content": content
        }
        
        # Merge extra metadata (e.g., epidora_coordinate)
        if kwargs:
            record.update(kwargs)
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            
        return message_id

    def get_log_uri(self) -> str:
        date_str = datetime.now().strftime("%Y-%m-%d")
        return f"logs/chat/{date_str}.jsonl"

    def get_recent_messages(self, limit: int = 10) -> list[Dict[str, Any]]:
        """
        Retrieves the last N messages from today's log for short-term memory context.
        Returns a list of dicts: [{'role': 'user'|'sophia', 'content': '...'}, ...]
        """
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self.log_dir, f"{date_str}.jsonl")
        
        if not os.path.exists(log_file):
            return []
            
        messages = []
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            record = json.loads(line)
                            messages.append({
                                "role": record.get("role", "unknown"),
                                "content": record.get("content", "")
                            })
                        except json.JSONDecodeError:
                            continue
                            
            return messages[-limit:]
        except Exception as e:
            print(f"[Logger] Failed to read recent messages: {e}")
            return []
