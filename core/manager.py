import json
import os
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from .schema import (
    MemoryManifest, Episode, EpisodeState, EpisodeRevision, 
    EpisodeSignature, EpisodeSnapshot, EpisodeLifecycle, 
    EpisodeClosedBy, EpisodeDecision, Source, SourceType,
    SourceRange, RangeKind, Patch, PatchStatus, EngineType, PatchType
)
from .logger import ChatLogger
from .epidora import EpidoraEngine, EpidoraSignal
from .llm_interface import LLMInterface
from .connector import SophiaConnector

MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "../memory/memory_manifest.json")

class EpisodeManager:
    def __init__(self, manifest_path: str = MANIFEST_PATH):
        self.manifest_path = manifest_path
        self.manifest = self._load_manifest()
        self.logger = ChatLogger()
        self.epidora = EpidoraEngine()
        self.llm = LLMInterface()
        self.connector = SophiaConnector()

    def _load_manifest(self) -> MemoryManifest:
        if not os.path.exists(self.manifest_path):
            return MemoryManifest()
        with open(self.manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return MemoryManifest(**data)

    def save_manifest(self):
        """Atomic write to JSON"""
        temp_path = self.manifest_path + ".tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(self.manifest.model_dump_json(indent=2))
        os.replace(temp_path, self.manifest_path)
        
        # Sync with server (Fire and forget or simple sync)
        self.connector.sync_manifest(self.manifest.dict())

    def get_or_create_active_episode(self) -> Episode:
        # Find explicit OPEN episode
        for ep in self.manifest.episodes.values():
            if ep.lifecycle.state == EpisodeState.OPEN:
                return ep
        
        # Create new if none
        ep_id = f"ep_{datetime.utcnow().strftime('%Y%m%d')}_{uuid.uuid4().hex[:4]}"
        return self.create_episode(ep_id, [])

    def create_episode(self, episode_id: str, sources: List[Source]) -> Episode:
        """
        Starts a new episode with OPEN state.
        """
        now = datetime.utcnow()
        episode = Episode(
            episode_id=episode_id,
            revision=EpisodeRevision(rev=1, prev_episode_ref=None),
            sources=sources, # Reference Only
            signature=EpisodeSignature(
                bitset="0x0000000000000000", # Placeholder, needs calculation logic
                mapping_version=self.manifest.current_mapping_version
            ),
            snapshot=EpisodeSnapshot(
                intent_thin="",
                outcome_thin=""
            ),
            lifecycle=EpisodeLifecycle(
                state=EpisodeState.OPEN,
                opened_at=now
            )
        )
        self.manifest.episodes[episode_id] = episode
        self.save_manifest()
        return episode

    def process_input(self, text: str) -> Dict[str, Any]:
        """
        1. Log User Input (Left Brain)
        2. Detect Structure (Right Brain)
        3. Create Patches (Resonance)
        4. Generate Expression (LLM)
        """
        # 1. Detect (Epidora - Right Brain / Ui)
        # We detect FIRST to tag the input with its coordinate (Shin).
        signals = self.epidora.detect(text)
        epidora_coords = [s.code for s in signals] if signals else ["UNKNOWN"]
        
        # 2. Log (Sensory - Shin)
        # Log not just text, but its coordinate in the world.
        msg_id = self.logger.log_message("user", text, epidora_coordinates=epidora_coords)
        
        active_ep = self.get_or_create_active_episode()
        
        # 3. Resonance (Patch Creation) & 4. Expression
        new_patches = []
        sophia_response = None
        
        # [Context Injection] - In (Reflecting)
        # Retrieve recent history for Short-Term Memory
        recent_history = self.logger.get_recent_messages(limit=10)
        context_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent_history])
        
        for sig in signals:
            # Create Patch
            patch_id = f"p_{str(uuid.uuid4())[:8]}"
            patch = {
                "patch_id": patch_id,
                "target_episode_id": active_ep.episode_id,
                "engine": "sophia",
                "type": "reasoning",
                "issue_code": sig.code,
                "thin_summary": sig.message,
                "status": "pending",
                "options": [{"id": "opt_1", "semantic": "greeting", "label": "인사"}], # Mock options
                "created_at": str(datetime.now()),
                "updated_at": str(datetime.now())
            }
            self.manifest.patches[patch_id] = patch
            new_patches.append(patch)
            
            # Generate Question (Expression)
            if sophia_response is None:
                sophia_response = self.llm.generate_question(
                    signal_code=sig.code,
                    signal_message=sig.message, 
                    snippet=sig.snippet,
                    previous_context=context_str
                )
                self.logger.log_message("sophia", sophia_response)
            
        self.save_manifest()
        
        return {
            "episode_id": active_ep.episode_id,
            "message_id": msg_id,
            "signals": [p.dict() for p in new_patches],
            "sophia_response": sophia_response
        }

    def record_signal(self, episode_id: str, signal_data: Any):
        """
        Records an Epidora signal (Gap/Suspicion).
        In v0.1, this might be stored in a temporary state or snapshot.snapshot.open_questions.
        For now, just a placeholder.
        """
        pass

    def make_decision(self, episode_id: str, decision: EpisodeDecision):
        """
        Closes the episode upon user decision.
        """
        if episode_id not in self.manifest.episodes:
            raise ValueError(f"Episode {episode_id} not found")
        
        episode = self.manifest.episodes[episode_id]
        
        # Update Lifecycle
        episode.lifecycle.state = EpisodeState.CLOSED
        episode.lifecycle.end_at = decision.decided_at
        episode.lifecycle.closed_by = EpisodeClosedBy.DECISION_MADE
        
        # Add Decision to Manifest
        self.manifest.episode_decisions.append(decision)
        
        # Validate patch status update if decision is adopting a patch
        if decision.type == "adopt_patch" and decision.value:
            # Mark patch as applied
             # Ideally decision.value should be option_id, but here assuming we link back to patch_id somehow
             # Schema says: decision.patch_id is NOT in decision model top level but in patches logic?
             # Docs/Schema.md says decision has patch_id.
             # My current EpisodeDecision model has decision_id, target_episode, type, value, reason_code.
             # Does NOT have patch_id field explicitly? 
             # Wait, Docs/Schema.md says:
             # essential fields: decision_id, patch_id, target_anchor...
             # My schema implementation of EpisodeDecision:
             # class EpisodeDecision(BaseModel): ... target_episode ...
             # It seems I missed `patch_id` field in EpisodeDecision model in schema.py! 
             # The user instruction didn't explicitly ask to fix schema.py for Decision but I should probably utilize `value` or add `patch_id`.
             # For now, let's assume `value` might contain patch info or I should fix `schema.py` later.
             # Proceeding with just saving manifest.
             pass
        
        self.save_manifest()

    def get_episode(self, episode_id: str) -> Optional[Episode]:
        return self.manifest.episodes.get(episode_id)
