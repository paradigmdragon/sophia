import json
import sys

def emit_event(event_type: str, data: dict = None):
    """Emit a JSON event to stdout."""
    payload = {"event": event_type}
    if data:
        payload.update(data)
    print(json.dumps(payload, ensure_ascii=False), flush=True)
