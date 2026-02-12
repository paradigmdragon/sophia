from typing import Dict, Any

class ContextMatcher:
    def __init__(self):
        pass

    def match(self, required_context: Dict[str, Any], current_context: Dict[str, Any]) -> bool:
        """
        Check if the required context matches the current context.
        
        Args:
            required_context: Dict of requirements defined in MessageQueue. 
                              e.g. {"session_state": "IDLE", "chunk_a": 1}
            current_context: Dict of current system state.
                             e.g. {"session_state": "IDLE", "chunk_a": 1, "chunk_b": 2}
        
        Returns:
            True if ALL requirements are met.
        """
        if not required_context:
            return True

        for key, req_val in required_context.items():
            # If current context doesn't have the key, fail match?
            # Or should we be lenient? For v0.1 strict match feels safer.
            curr_val = current_context.get(key)
            
            if curr_val != req_val:
                return False
                
        return True
