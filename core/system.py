from typing import Dict, Any, List, Optional
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from core.engine.schema import Base
from core.engine.workflow import WorkflowEngine

class SophiaSystem:
    def __init__(self, db_path: str = "sqlite:///sophia.db"):
        self.db_path = db_path
        self.engine = create_engine(db_path)
        # Ensure tables exist
        Base.metadata.create_all(self.engine)
        self._ensure_runtime_indexes()
        self.Session = sessionmaker(bind=self.engine)
        
        # Initialize Core Engines
        # WorkflowEngine initializes HeartEngine internally
        self.workflow = WorkflowEngine(self._get_session)
        self.heart = self.workflow.heart

    def _ensure_runtime_indexes(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_candidate_episode_status ON candidates (episode_id, status)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_candidate_proposed_at ON candidates (proposed_at)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_event_type_at ON events (type, at)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_event_episode_type_at ON events (episode_id, type, at)"))

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

    def reject(self, episode_id: str, candidate_id: str, reason: str | None = None) -> bool:
        """Reject a candidate."""
        return self.workflow.reject(episode_id, candidate_id, reason=reason)

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

    def move_file(self, old_path: str, new_path: str) -> bool:
        """
        Move a file/folder physically and update DB references.
        """
        import shutil
        import os
        from core.engine.schema import Episode
        
        # 1. Physical Move
        try:
            # Check exist
            if not os.path.exists(old_path):
                print(f"[System] Move failed: Source not found {old_path}")
                return False
            
            # If folder, ensure parent of new_path exists
            new_parent = os.path.dirname(new_path)
            if not os.path.exists(new_parent):
                os.makedirs(new_parent)
                
            shutil.move(old_path, new_path)
            print(f"[System] Physical move successful: {old_path} -> {new_path}")
        except Exception as e:
            print(f"[System] Physical move failed: {e}")
            return False

        # 2. DB Update
        session = self._get_session()
        try:
            # Update Episode log_ref
            # We need to find episodes where log_ref['uri'] starts with old_path
            # Since JSON query is specific to dialect, we fetch and filter in python for sqlite compatibility
            # Optimized for v0.1: Fetch all episodes, check URI.
            # If many episodes, this is slow. But v0.1 has few.
            
            episodes = session.query(Episode).all()
            updated_count = 0
            
            for ep in episodes:
                uri = ep.log_ref.get('uri')
                if uri and uri.startswith(old_path):
                    # Replace prefix
                    new_uri = uri.replace(old_path, new_path, 1)
                    ep.log_ref = {**ep.log_ref, 'uri': new_uri}
                    updated_count += 1
            
            if updated_count > 0:
                session.commit()
                print(f"[System] DB Updated: {updated_count} episodes relocated.")
            
            return True
        except Exception as e:
            print(f"[System] DB Update failed: {e}")
            session.rollback()
            return True # Physical move succeeded, so return True but warn?
        finally:
            session.close()

    def get_graph_data(self) -> Dict[str, Any]:
        """
        Returns Blueprint Graph Data (Nodes, Links) for visualization.
        """
        from core.engine.blueprint import BlueprintEngine
        blueprint = BlueprintEngine()
        blueprint.scan() # Audit code
        return blueprint.get_graph_data()
        
    def get_blueprint_report(self) -> List[str]:
        """
        Returns list of missing features.
        """
        from core.engine.blueprint import BlueprintEngine
        blueprint = BlueprintEngine()
        blueprint.scan()
        return blueprint.missing_features
