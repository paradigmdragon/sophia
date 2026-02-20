from typing import List, Dict, Optional
import re

class EpidoraValidator:
    """
    Validator for detecting Epidora Structural Errors (The 6 Paradoxes).
    Currently implements Error 1 (Fixed Language) and Error 4 (Discretization).
    """

    def __init__(self):
        self.error_patterns = {
            1: {
                "name": "Fixed Language (Error 1)",
                "description": "Treating dynamic processes as immutable static categories.",
                "patterns": [
                    r"\b(is|are) always\b",
                    r"\b(is|are) never\b",
                    r"\bcannot change\b",
                    r"\bmust always be\b",
                    r"\bimmutable\b",
                    r"\bfixed forever\b"
                ]
            },
            4: {
                "name": "Discretization (Error 4)",
                "description": "Forcing continuous processes into binary states (0/1, True/False).",
                "patterns": [
                    r"\b(either|neither).+or\b",
                    r"\bis (this|it|that) (.+) or (.+)\?",
                    r"\b(is|are) (good|bad)\b",
                    r"\b(good|bad) or (good|bad)\b",
                    r"\b(true|false)\b",
                    r"\b(0|1)\b",
                    r"\b(black|white)\b"
                ]
            }
        }

    def validate(self, content: str) -> List[Dict]:
        """
        Analyze content for structural errors.
        Returns a list of detected errors with metadata.
        """
        detected_errors = []
        
        # Check Error 1: Fixed Language
        for pattern in self.error_patterns[1]["patterns"]:
            if re.search(pattern, content, re.IGNORECASE):
                detected_errors.append({
                    "error_id": 1,
                    "name": self.error_patterns[1]["name"],
                    "description": self.error_patterns[1]["description"],
                    "match": pattern,
                    "suggestion": "Consider if this state is temporary or context-dependent."
                })
                break # Dedup per error type

        # Check Error 4: Discretization
        for pattern in self.error_patterns[4]["patterns"]:
            if re.search(pattern, content, re.IGNORECASE):
                detected_errors.append({
                    "error_id": 4,
                    "name": self.error_patterns[4]["name"],
                    "description": self.error_patterns[4]["description"],
                    "match": pattern,
                    "suggestion": "Consider if there is a spectrum or process between these two states."
                })
                break
                
        return detected_errors

    def get_philosophical_feedback(self, error_id: int) -> str:
        """
        Returns a 'Revealing' question based on the error.
        """
        if error_id == 1:
            return "Does this definition hold true in all contexts, or is it evolving?"
        elif error_id == 4:
            return "Are these the only two options, or is there a transition between them?"
        return "Observe the structure of this thought."
