from typing import List, Dict
from core.engine.schema import Episode, Candidate
from core.engine.constants import ChunkA, ChunkB, ChunkC, ChunkD, FacetID, FacetValueCertainty, FacetValueSource, FacetValueAbstraction

class CandidateEncoder:
    """
    Candidate Generator (Phase 0 Stub)
    
    In a real implementation, this would call an LLM with the Seed Value Map System Prompt.
    For Phase 0, this is a deterministic rule-based generator or manual injector.
    """
    
    def _classify_intent(self, text: str) -> str:
        """
        Simple Rule-Based Intent Classifier.
        Returns: INTENT_GREETING, INTENT_ACK, INTENT_UNKNOWN
        """
        t = text.strip().lower()
        if not t:
            return "INTENT_UNKNOWN"
            
        # Greeting
        greetings = ["hello", "hi", "hey", "sophia", "안녕", "안녕하세요", "반가워", "ㅎㅇ"]
        if t in greetings or any(t.startswith(g) for g in greetings if len(t) < 10):
            return "INTENT_GREETING"
            
        # Acknowledgment (Short 1-word or specific phrases)
        acks = ["yes", "no", "okay", "ok", "good", "bad", "네", "아니요", "응", "어", "ㅇㅇ", "좋아", "싫어"]
        if t in acks:
            return "INTENT_ACK"
            
        # 1-Word input that isn't a backbone trigger -> Treat as ACK/Low-level
        if len(t.split()) == 1 and len(t) < 10:
            return "INTENT_ACK"
            
        return "INTENT_UNKNOWN"

    def generate_candidates(self, text: str, source: str = "encoder") -> List[Dict]:
        """
        Mock implementation:
        1. Classify Intent.
        2. If Special Intent, bypass Semantic Analyzer (Backbone Generation).
        3. Else, propose relevant Backbones.
        """
        candidates = []
        intent = self._classify_intent(text)
        
        # 1. Bypass Logic
        if intent == "INTENT_GREETING":
            candidates.append({
                "backbone_bits": 0x0000,
                "facets": [],
                "note": "Conversation", # Signal for API to auto-reply with greeting
                "confidence": 100,
                "status": "PENDING"
            })
            return candidates
            
        if intent == "INTENT_ACK":
            candidates.append({
                "backbone_bits": 0x0000,
                "facets": [],
                "note": "Acknowledgment", # Signal for API to auto-reply with simple ack
                "confidence": 100,
                "status": "PENDING"
            })
            return candidates

        # 2. Semantic Analysis (Backbone Generation)
        # Example 1: Project Plan keywords -> PROCESS / SEQUENCE
        if "plan" in text.lower() or "roadmap" in text.lower():
            candidates.append({
                "backbone_bits": (ChunkA.PROCESS << 12) | (ChunkB.HYPOTHETICAL << 8) | (ChunkC.SEQUENCE << 4) | (ChunkD.COMPOSITIONAL),
                "facets": [
                    {"id": FacetID.CERTAINTY, "value": FacetValueCertainty.PENDING},
                    {"id": FacetID.ABSTRACTION, "value": FacetValueAbstraction.PATTERN},
                    {"id": FacetID.SOURCE, "value": FacetValueSource.DOCUMENT}
                ],
                "note": "Detected planning context",
                "confidence": 80
            })
            
        # Example 2: Defined Rule -> PRINCIPLE / TIMELESS
        if "rule" in text.lower() or "must" in text.lower() or "principle" in text.lower():
            candidates.append({
                "backbone_bits": (ChunkA.PRINCIPLE << 12) | (ChunkB.STRUCTURAL << 8) | (ChunkC.TIMELESS << 4) | (ChunkD.EQUIVALENCE),
                "facets": [
                    {"id": FacetID.CERTAINTY, "value": FacetValueCertainty.PENDING},
                    {"id": FacetID.ABSTRACTION, "value": FacetValueAbstraction.AXIOM},
                    {"id": FacetID.SOURCE, "value": FacetValueSource.DOCUMENT}
                ],
                "note": "Detected axiomatic rule",
                "confidence": 85
            })

        # Default fallback if no keywords match (UNKNOWN)
        if not candidates:
             candidates.append({
                "backbone_bits": 0x0000, # All UNKNOWN
                "facets": [
                    {"id": FacetID.CERTAINTY, "value": FacetValueCertainty.PENDING},
                ],
                "note": "Default fallback",
                "confidence": 20
            })
            
        return candidates
