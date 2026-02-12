import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from core.engine.schema import MessageQueue, Episode
from core.engine.dispatcher import HeartDispatcher

class HeartEngine:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.dispatcher = HeartDispatcher()

    def set_state(self, state: str):
        old_state = self.dispatcher.state
        self.dispatcher.set_state(state)
        if state == "IDLE" and old_state != "IDLE":
             # Auto-Push Loop Trigger
             print("[Heart] State changed to IDLE. Triggering Auto-Push check...")
             self.dispatch(current_context={"session_state": "IDLE"})

    def dispatch(self, current_context: Dict[str, Any] = {}) -> Optional[MessageQueue]:
        """
        Attempt to dispatch the next message.
        Args:
            current_context: Dict of external context (e.g. chunk_a: 1)
        """
        session = self._get_session()
        try:
            msg = self.dispatcher.get_next_message(session, current_context)
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
                
                # If summary exists, return a modified copy or stick with original object?
                # For CLI display, we can just attach the summary content to the object temporarily
                if getattr(msg, 'summary_content', None):
                    msg.content = msg.summary_content
                    
                return msg
            return None
        finally:
            session.close()

    def get_status_summary(self) -> Dict:
        """
        Get Queue counts and Cooldown status.
        """
        session = self._get_session()
        try:
            # Queue Counts by Priority
            counts = {
                "P1": session.query(MessageQueue).filter_by(status='PENDING', priority='P1').count(),
                "P2": session.query(MessageQueue).filter_by(status='PENDING', priority='P2').count(),
                "P3": session.query(MessageQueue).filter_by(status='PENDING', priority='P3').count(),
                "P4": session.query(MessageQueue).filter_by(status='PENDING', priority='P4').count(),
            }
            
            # Cooldown Status
            cooldowns = self.dispatcher.get_cooldown_status()
            
            return {
                "state": self.dispatcher.state,
                "queue_counts": counts,
                "cooldown_status": cooldowns
            }
        finally:
            session.close()

    def _get_session(self):
        return self.session_factory()

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
