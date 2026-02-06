from typing import List, Any
from .line_wrap import wrap_text, LineWrapOptions
from app.config import get_config
from app.common.utils import get_logger
from app.refine.rules import RefineRules
from app.common.writer import Writer
import json

logger = get_logger("Refiner")

class Refiner:
    def __init__(self):
        self.rules = RefineRules()
        self.writer = Writer()

    def refine(self, segments: List[Any], base_output_path: str, config: dict = None) -> dict:
        """
        Refine segments and return paths to generated files.
        """
        logger.info(f"Refining output for: {base_output_path}...")
        
        # Load config if not provided
        if config is None:
            config = get_config()

        # 1. Merge Segments (Logic handles conversion to dict)
        merged_segments = self.rules.merge_segments(segments)
        
        # Prepare Line Wrap Options
        line_wrap_config = config.get("refine", {}).get("line_wrap", {})
        wrap_options = LineWrapOptions(line_wrap_config)
        
        if wrap_options.enabled:
            logger.info(f"Line wrapping enabled (Max chars: {wrap_options.max_chars})")

        # 2. Text Cleaning & Line Wrapping
        refined_segments = []
        for seg in merged_segments:
            cleaned_text = self.rules.remove_repetitions(seg["text"])
            
            # Apply Line Wrap
            if wrap_options.enabled:
                cleaned_text = wrap_text(cleaned_text, wrap_options)

            seg["text"] = cleaned_text
            refined_segments.append(seg)
            
        # 3. Output Paths
        refined_srt_path = f"{base_output_path}.refined.srt"
        refined_txt_path = f"{base_output_path}.refined.txt"
        refine_log_path = f"{base_output_path}.refine.log.json"
        
        # 4. Write
        self._write_refined_srt(refined_segments, refined_srt_path)
        self._write_refined_txt(refined_segments, refined_txt_path)
        
        # Log stats
        log_data = {
            "original_segments": len(segments),
            "refined_segments": len(refined_segments),
            "algorithm": "rule_based_v1",
            "line_wrap": wrap_options.enabled
        }
        with open(refine_log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
            
        logger.info("Refinement completed.")
        return {
            "refined_srt": refined_srt_path,
            "refined_txt": refined_txt_path,
            "refine_log": refine_log_path
        }

    def _write_refined_srt(self, segments: List[dict], path: str):
        # We need to adapt this since Writer expects objects with start/end/text attributes usually
        # But we are reusing Writer logic or implementing here?
        # Let's reuse Writer format_timestamp logical but for dicts.
        # Writer.write_srt expects objects. Let's make a simple wrapper.
        
        class SegmentWrapper:
            def __init__(self, d):
                self.start = d['start']
                self.end = d['end']
                self.text = d['text']
                
        wrapped = [SegmentWrapper(s) for s in segments]
        self.writer.write_srt(wrapped, path)

    def _write_refined_txt(self, segments: List[dict], path: str):
        class SegmentWrapper:
            def __init__(self, d):
                self.text = d['text']
        
        wrapped = [SegmentWrapper(s) for s in segments]
        self.writer.write_txt(wrapped, path)
