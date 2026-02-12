from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
from core.engine.schema import MessageQueue
from core.engine.context import ContextMatcher

import json
import os

STATE_FILE = "heart_state.json"

class HeartDispatcher:
    def __init__(self):
        # Default State
        self.state = "FOCUS" # FOCUS, WRITING, IDLE
        self.context_matcher = ContextMatcher()
        
        # Cooldowns (in minutes)
        self.cooldown_limits = {
            "P1": 10,
            "P2": 30,
            "P3": 30,
            "P4": 30
        }
        
        # Last Sent Timestamps
        self.last_sent = {
            "P1": None,
            "P2": None,
            "P3": None,
            "P4": None
        }
        
        self._load_state()

    def _load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    data = json.load(f)
                    self.state = data.get("state", "FOCUS")
                    last_sent_iso = data.get("last_sent", {})
                    for p, iso in last_sent_iso.items():
                        if iso:
                            self.last_sent[p] = datetime.fromisoformat(iso)
            except Exception as e:
                print(f"[Dispatcher] Failed to load state: {e}")

    def _save_state(self):
        try:
            last_sent_iso = {
                p: (dt.isoformat() if dt else None) 
                for p, dt in self.last_sent.items()
            }
            data = {
                "state": self.state,
                "last_sent": last_sent_iso
            }
            with open(STATE_FILE, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"[Dispatcher] Failed to save state: {e}")

    def set_state(self, state: str):
        self.state = state
        self._save_state()

    def get_cooldown_status(self) -> Dict[str, float]:
        """Returns remaining cooldown seconds for each priority"""
        now = datetime.now()
        status = {}
        for p, last_time in self.last_sent.items():
            if last_time is None:
                status[p] = 0
                continue
            
            elapsed = (now - last_time).total_seconds()
            limit = self.cooldown_limits[p] * 60
            remaining = max(0, limit - elapsed)
            status[p] = remaining
        return status

    def _check_gate(self, priority: str) -> bool:
        """
        Check if message can pass the gate based on current state.
        FOCUS/WRITING: Only P1 allowed.
        IDLE: All allowed.
        """
        if self.state in ["FOCUS", "WRITING"]:
            return priority == "P1"
        return True

    def _check_cooldown(self, priority: str) -> bool:
        """Check if priority bucket is ready"""
        last = self.last_sent.get(priority)
        if last is None:
            return True
            
        limit = self.cooldown_limits.get(priority, 30) * 60
        elapsed = (datetime.now() - last).total_seconds()
        return elapsed >= limit

    def get_next_message(self, session, current_context: Dict[str, Any] = {}) -> Optional[MessageQueue]:
        """
        Fetch next available message from DB respecting Gate and Cooldown.
        Returns a single MessageQueue object (or a summary placeholder).
        Args:
            current_context: Dict of current system state (e.g. {"session_state": "IDLE"})
        """
        # 1. Get all pending messages ordered by priority
        pending = session.query(MessageQueue).filter_by(status='PENDING')\
            .order_by(MessageQueue.priority.asc(), MessageQueue.created_at.asc()).all()

        # Update context with internal state if not provided?
        context = current_context.copy()
        if "session_state" not in context:
             context["session_state"] = self.state

        for msg in pending:
            # 2. Gate Check (Priority/State based)
            if not self._check_gate(msg.priority):
                continue

            # 3. Context Match Check (using ContextMatcher)
            if msg.required_context:
                # We need to ensure we don't break if msg.required_context is None (handled by "if msg.required_context")
                # But wait, schema says JSON, nullable=True. Empty JSON {} or None.
                if not self.context_matcher.match(msg.required_context, context):
                    continue

            # 4. Cooldown Check
            if not self._check_cooldown(msg.priority):
                continue
            
            # 5. Batching Check (For P2-P4)
            if msg.priority in ["P2", "P3", "P4"] and msg.episode_id:
                # Count messages for this episode
                batch = [m for m in pending if m.episode_id == msg.episode_id and m.priority in ["P2", "P3", "P4"]]
                if len(batch) > 1:
                    # Create Summary Info (Do not overwrite content in DB)
                    msg.summary_content = f"{len(batch)} new updates for Episode {msg.episode_id}."
                    msg.batched_ids = [m.message_id for m in batch]
                    return msg

            # 4. Success - Return individual
            msg.batched_ids = [msg.message_id]
            msg.summary_content = None # Ensure attribute exists
            return msg
        
        return None

    def mark_dispatched(self, priority: str):
        """Update last sent timestamp for the priority bucket"""
        self.last_sent[priority] = datetime.now()
        self._save_state()
