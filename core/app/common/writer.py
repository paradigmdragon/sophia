import os
import json
import math
from typing import List, Any
from app.common.utils import get_logger

logger = get_logger("Writer")

class Writer:
    def format_timestamp(self, seconds: float) -> str:
        """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)."""
        hours = math.floor(seconds / 3600)
        seconds %= 3600
        minutes = math.floor(seconds / 60)
        seconds %= 60
        milliseconds = round((seconds - math.floor(seconds)) * 1000)
        seconds = math.floor(seconds)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    def write_srt(self, segments: List[Any], output_path: str):
        """Write segments to SRT file."""
        with open(output_path, "w", encoding="utf-8") as f:
            for index, segment in enumerate(segments, start=1):
                start = self.format_timestamp(segment.start)
                end = self.format_timestamp(segment.end)
                text = segment.text.strip()
                f.write(f"{index}\n{start} --> {end}\n{text}\n\n")
        logger.info(f"Saved SRT: {output_path}")

    def write_txt(self, segments: List[Any], output_path: str):
        """Write text only."""
        with open(output_path, "w", encoding="utf-8") as f:
            for segment in segments:
                f.write(segment.text.strip() + "\n")
        logger.info(f"Saved TXT: {output_path}")

    def write_log(self, log_data: dict, output_path: str):
        """Write execution log to JSON."""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved Log: {output_path}")
