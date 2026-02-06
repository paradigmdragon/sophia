import re
from typing import List, Dict, Any

class RefineRules:
    @staticmethod
    def remove_repetitions(text: str) -> str:
        """
        Remove simple immediate repetitions like '음.. 음..', '그.. 그..'.
        This uses basic regex for 1-2 word repetitions.
        """
        if not text:
            return ""
            
        # Remove consecutive duplicate words (e.g., "그 그", "저 저")
        # \b(\w+)\s+\1\b -> matches "word word"
        text = re.sub(r'\b(\w+)\s+\1\b', r'\1', text, flags=re.IGNORECASE)
        
        # Remove repeated phrases with punctuation (e.g. "음.. 음..")
        # This is harder with regex alone without nlp, but we can try simple pattern
        # Simple heuristic: split by space, check neighbors
        words = text.split()
        if len(words) < 2:
            return text
            
        cleaned_words = []
        prev_word = None
        
        for word in words:
            # Normalize for comparison (remove basic punctuation)
            norm_word = re.sub(r'[.,!?~]', '', word)
            norm_prev = re.sub(r'[.,!?~]', '', prev_word) if prev_word else None
            
            if norm_word == norm_prev and len(norm_word) <= 2:
                # Skip repetition if short word (<= 2 chars)
                continue
            
            cleaned_words.append(word)
            prev_word = word
            
        return " ".join(cleaned_words)

    @staticmethod
    def merge_segments(segments: List[Any], gap_threshold: float = 0.5, max_duration: float = 10.0) -> List[Dict[str, Any]]:
        """
        Merge short segments into larger sentences based on time gaps and punctuation.
        This is a simplified logic for v0.1.3.
        
        segments: List of whisper segments (objects) or dicts
        """
        if not segments:
            return []

        merged = []
        current_group = []
        
        for seg in segments:
            # Normalize input to dict
            seg_dict = {
                "start": seg.start if hasattr(seg, 'start') else seg['start'],
                "end": seg.end if hasattr(seg, 'end') else seg['end'],
                "text": seg.text.strip() if hasattr(seg, 'text') else seg['text']
            }
            
            if not current_group:
                current_group.append(seg_dict)
                continue
                
            last_seg = current_group[-1]
            time_gap = seg_dict["start"] - last_seg["end"]
            current_duration = last_seg["end"] - current_group[0]["start"]
            
            # Merge condition: small gap AND not too long AND previous doesn't end with sentence terminator
            is_sentence_end = last_seg["text"].endswith(('?', '!', '.', '\n'))
            
            if time_gap < gap_threshold and current_duration < max_duration and not is_sentence_end:
                current_group.append(seg_dict)
                # Extend the last segment in group effectively? 
                # Actually we aggregate later.
            else:
                # Flush current group
                merged.append(RefineRules._aggregate_group(current_group))
                current_group = [seg_dict]
                
        if current_group:
             merged.append(RefineRules._aggregate_group(current_group))
             
        return merged

    @staticmethod
    def _aggregate_group(group: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not group:
            return {}
            
        start = group[0]["start"]
        end = group[-1]["end"]
        # Join text
        text_parts = [g["text"] for g in group]
        full_text = " ".join(text_parts)
        
        return {
            "start": start,
            "end": end,
            "text": full_text
        }
