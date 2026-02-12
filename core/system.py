from typing import Dict, Any, List, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.engine.schema import Base
from core.engine.workflow import WorkflowEngine

class SophiaSystem:
    def __init__(self, db_path: str = "sqlite:///sophia.db"):
        self.db_path = db_path
        self.engine = create_engine(db_path)
        # Ensure tables exist
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        
        # Initialize Core Engines
        # WorkflowEngine initializes HeartEngine internally
        self.workflow = WorkflowEngine(self._get_session)
        self.heart = self.workflow.heart

    def _get_session(self):
        return self.Session()

    def ingest(self, ref_uri: str) -> str:
        """Create a new episode from a reference URI."""
        return self.workflow.ingest(ref_uri)

    def propose(self, episode_id: str, text: str = "") -> List[str]:
        """
        Generate and save candidates for an episode based on text context.
        Uses the Encoder (simulated or real).
        """
        # For v0.1 we simulate encoder input via text if needed, 
        # or just delegates to workflow.propose which uses Encoder internally.
        # Workflow.propose expects a list of candidate dicts OR uses encoder?
        # Let's check workflow.propose signature. 
        # It takes `candidates_data: List[Dict]`.
        # So we need to use the Encoder here to get the data first.
        from core.engine.encoder import CandidateEncoder
        encoder = CandidateEncoder()
        candidates_data = encoder.generate_candidates(text)
        return self.workflow.propose(episode_id, candidates_data, source="api_user")

    def adopt(self, episode_id: str, candidate_id: str) -> str:
        """Adopt a candidate as a Backbone."""
        return self.workflow.adopt(episode_id, candidate_id)

    def reject(self, episode_id: str, candidate_id: str) -> bool:
        """Reject a candidate."""
        return self.workflow.reject(episode_id, candidate_id)

    def get_heart_status(self) -> Dict[str, Any]:
        """Get Heart Engine status summary."""
        return self.heart.get_status_summary()

    def dispatch_heart(self, context: Dict[str, Any] = {}) -> Optional[Dict[str, Any]]:
        """
        Trigger Heart Dispatch manually.
        Returns serialized message dict or None.
        """
        msg = self.heart.dispatch(context)
        if msg:
            return {
                "message_id": msg.message_id,
                "priority": msg.priority,
                "type": msg.type,
                "intent": msg.sone_intent,
                "content": msg.content,
                "created_at": msg.created_at.isoformat() if msg.created_at else None
            }
        return None

    def set_heart_state(self, state: str):
        """Set Heart Session State (FOCUS, IDLE, etc)."""
        self.heart.set_state(state)

    def get_candidate(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        """Get Candidate details by ID."""
        session = self._get_session()
        try:
            from core.engine.schema import Candidate
            candidate = session.query(Candidate).filter_by(candidate_id=candidate_id).first()
            if candidate:
                return {
                    "candidate_id": candidate.candidate_id,
                    "confidence": candidate.confidence,
                    "note_thin": candidate.note_thin,
                    "backbone_bits": candidate.backbone_bits,
                    "status": candidate.status
                }
            return None
        finally:
            session.close()
