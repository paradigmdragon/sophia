import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from core.engine.schema import MessageQueue, Episode
from core.engine.dispatcher import HeartDispatcher
from core.engine.schema import MessageQueue, Episode
from core.engine.dispatcher import HeartDispatcher
from core.logger import ChatLogger
from core.engine.skill_bridge import SkillBridge

class HeartEngine:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.dispatcher = HeartDispatcher()
        self.logger = ChatLogger()

    def dump_mind_state(self):
        """
        Writes the current Heart Engine state to forest/project/sophia/state/sophia_mind.md.
        This provides a real-time view for the user.
        """
        from core.engine.constants import SOPHIA_MIND
        filepath = SOPHIA_MIND
        
        # Gather Data
        status = self.get_status_summary()
        state = status["state"]
        counts = status["queue_counts"]
        
        # Get Next Question / Current Focus
        # For v0.1 we peek at P1 queue or active context
        next_q = "None"
        pending_p1 = self.get_pending_messages(limit=1)
        if pending_p1:
            next_q = f"[{pending_p1[0]['type']}] {pending_p1[0]['content']}"
            
        # Blueprint Audit
        from core.system import SophiaSystem
        sys = SophiaSystem()
        missing_features = sys.get_blueprint_report()
        missing_md = ""
        if missing_features:
            missing_md = "## ⚠️ Blueprint Gaps\n" + "\n".join([f"- [ ] {f}" for f in missing_features[:5]])
            if len(missing_features) > 5:
                missing_md += f"\n- ... and {len(missing_features)-5} more."
        else:
            missing_md = "## ✅ Blueprint Status\n- All specs implemented."
        
        md_content = f"""# Sophia Mind State
**Last Updated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 🧠 Cognitive State
- **Mode**: `{state}`
- **Active Context**: `Global`

## 🎯 Next Action
**{next_q}**

{missing_md}

## 📨 Message Queue
| Priority | Count | Status |
| :--- | :---: | :--- |
| **P1 (Critical)** | {counts['P1']} | {'🔴 Backlog' if counts['P1']>0 else '🟢 Clear'} |
| **P2 (High)** | {counts['P2']} | {'🟠 Backlog' if counts['P2']>0 else '🟢 Clear'} |
| **P3 (Normal)** | {counts['P3']} | - |
| **P4 (Background)** | {counts['P4']} | - |

## ⏳ Cooldowns
- **Global**: {status['cooldown_status'].get('global', 'Ready')}
"""
        try:
            with open(filepath, "w") as f:
                f.write(md_content)
        except Exception as e:
            print(f"[Heart] Failed to dump mind state: {e}")

    def dispatch(self, current_context: Dict[str, Any] = {}) -> Optional[MessageQueue]:
        """
        Attempt to dispatch the next message.
        Args:
            current_context: Dict of external context (e.g. chunk_a: 1)
        """
        session = self._get_session()
        try:
            msg = self.dispatcher.get_next_message(session, current_context)
            
            # Hook: Update Mind State on every dispatch attempt (or at least when msg found)
            # To avoid IO thrashing, maybe only if msg found or state changes?
            # User wants "Real-time", so let's do it if msg found or periodically.
            # But dispatch is called often. Let's do it if msg found.
            
            if msg:
                # Mark as SERVED and update cooldown
                batched_ids = getattr(msg, 'batched_ids', [msg.message_id])
                session.query(MessageQueue).filter(MessageQueue.message_id.in_(batched_ids)).update(
                    {MessageQueue.status: 'SERVED'}, synchronize_session=False
                )
                
                self.dispatcher.mark_dispatched(msg.priority)
                session.commit()
                
                content_to_show = getattr(msg, 'summary_content', msg.content)
                if content_to_show is None: # Fallback
                     content_to_show = msg.content
                     
                print(f"[Heart] DISPATCHED: [{msg.priority}] {content_to_show}")
                
                # Log to Chat History (JSONL) so UI can see it
                # We use role='sophia' but add metadata to distinguish
                self.logger.log_message(
                    role="sophia",
                    content=str(content_to_show),
                    intent=msg.sone_intent,
                    context=msg.required_context,
                    priority=msg.priority,
                    message_type=msg.type 
                )
                
                # If summary exists, return a modified copy or stick with original object?
                # For CLI display, we can just attach the summary content to the object temporarily
                if getattr(msg, 'summary_content', None):
                    msg.content = msg.summary_content
                
                self.dump_mind_state() # Update monitor
                return msg
                
            return None
        finally:
            session.close()

    def set_state(self, state: str):
        old_state = self.dispatcher.state
        self.dispatcher.set_state(state)
        if state == "IDLE" and old_state != "IDLE":
             # Auto-Push Loop Trigger
             print("[Heart] State changed to IDLE. Triggering Auto-Push check...")
             self.dispatch(current_context={"session_state": "IDLE"})
        
        # Skill Bridge: Check if new state triggers external logic
        SkillBridge().check_and_trigger(state, {"source": "heart_state_change", "old_state": old_state})

        self.dump_mind_state() # Update monitor

    def trigger_message(self, 
                        priority: str, 
                        type: str, 
                        intent: str, 
                        content: str, 
                        episode_id: Optional[str] = None,
                        context: Optional[Dict] = None) -> str:
        """
        Enqueue a message to the MessageQueue.
        
        Args:
            priority: P1, P2, P3, P4
            type: ASK, CONFIRM, NOTICE, EXPORT_REQUEST
            intent: internal intent key (e.g. "conflict_check")
            content: human readable message
            episode_id: related episode
            context: additional context (e.g. session_state)
        """
        session = self._get_session()
        try:
            # Deduplication: Check if pending message with same intent/episode exists
            existing = session.query(MessageQueue).filter_by(
                sone_intent=intent, 
                episode_id=episode_id, 
                status='PENDING'
            ).first()
            
            if existing:
                context_str = f" (Episode: {episode_id})" if episode_id else ""
                print(f"[Heart] Duplicate message suppressed: {intent}{context_str}")
                return existing.message_id

            msg_id = f"msg_{uuid.uuid4().hex[:8]}"
            message = MessageQueue(
                message_id=msg_id,
                episode_id=episode_id,
                priority=priority,
                type=type,
                sone_intent=intent,
                content=content,
                required_context=context,
                status='PENDING'
            )
            session.add(message)
            session.commit()
            print(f"[Heart] Message Enqueued: [{priority}] {content}")
            
            self.dump_mind_state() # Update monitor
            return msg_id
        finally:
            session.close()

    def get_pending_messages(self, limit: int = 10) -> List[Dict]:
        """
        Fetch pending messages ordered by Priority (P1 > P2...) and Creation Time.
        Simple Fetch for Phase 0.
        """
        session = self._get_session()
        try:
            # Priority sort: P1 < P2 < P3 < P4 (String comaprison works: P1 < P2)
            messages = session.query(MessageQueue).filter_by(status='PENDING')\
                .order_by(MessageQueue.priority.asc(), MessageQueue.created_at.asc())\
                .limit(limit).all()
            
            return [
                {
                    "id": m.message_id,
                    "priority": m.priority,
                    "type": m.type,
                    "content": m.content,
                    "episode_id": m.episode_id
                }
                for m in messages
            ]
        finally:
            session.close()
