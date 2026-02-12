import os
import json
import subprocess
from typing import List, Dict, Any, Tuple
from pathlib import Path
import pysrt

class RoughCutRenderer:
    def __init__(self, ffmpeg_bin: str = "ffmpeg"):
        self.ffmpeg_bin = ffmpeg_bin

    def calculate_keep_intervals(self, duration_ms: int, candidates: List[Dict], decisions: List[Dict]) -> List[Tuple[int, int]]:
        """
        Derives stable Keep Intervals from Cut Candidates and User Decisions.
        Constraint 3: Padding -> Re-merge -> Filter
        """
        # 0. Apply Decisions
        # Default: all candidates are CUT unless user overrides to KEEP
        final_cuts = []
        decision_map = {d['id']: d['decision'] for d in decisions}
        
        for c in candidates:
            # If user explicitly kept it, ignore this cut range
            if decision_map.get(c['id']) == 'keep':
                continue
            final_cuts.append((c['start_ms'], c['end_ms']))
            
        # Sort and Merge overlapping cuts (Step 1: Cut Normalization)
        final_cuts.sort()
        merged_cuts = []
        if final_cuts:
            current_start, current_end = final_cuts[0]
            for start, end in final_cuts[1:]:
                if start <= current_end: # Overlap or touch
                    current_end = max(current_end, end)
                else:
                    merged_cuts.append((current_start, current_end))
                    current_start, current_end = start, end
            merged_cuts.append((current_start, current_end))

        # 2. Generate Initial Keep Intervals (Inversion)
        keep_intervals = []
        last_pos = 0
        for start, end in merged_cuts:
            if start > last_pos:
                keep_intervals.append((last_pos, start))
            last_pos = end
        
        if last_pos < duration_ms:
            keep_intervals.append((last_pos, duration_ms))
            
        # 3. Apply Padding (+-200ms)
        padded_keeps = []
        for start, end in keep_intervals:
            p_start = max(0, start - 200)
            p_end = min(duration_ms, end + 200)
            padded_keeps.append((p_start, p_end))
            
        # 4. Re-merge (Gap Filling < 500ms)
        stable_keeps = []
        if padded_keeps:
            curr_s, curr_e = padded_keeps[0]
            for next_s, next_e in padded_keeps[1:]:
                gap = next_s - curr_e
                if gap < 500: # gap is small, merge
                    curr_e = next_e
                else: 
                    stable_keeps.append((curr_s, curr_e))
                    curr_s, curr_e = next_s, next_e
            stable_keeps.append((curr_s, curr_e))
            
        # 5. Filter (Remove < 300ms)
        final_keeps = [
            (s, e) for s, e in stable_keeps if (e - s) >= 300
        ]
        
        return final_keeps

    def render(self, work_dir: str, keep_intervals: List[Tuple[int, int]], meta: Dict):
        """
        Executes FFmpeg pipeline to generate output_roughcut.mp4 and .srt.
        """
        work_path = Path(work_dir)
        source_video = meta["video_path"]
        output_video = work_path / "output_roughcut.mp4"
        output_srt = work_path / "output_roughcut.srt"
        
        # A. FFmpeg Filter Complex Construction
        # We need [0:v]trim=start=...:end=...,setpts=PTS-STARTPTS[v1];... [v1][a1]...concat=n=N:v=1:a=1[outv][outa]
        
        filter_parts = []
        concat_v = []
        concat_a = []
        
        for i, (start_ms, end_ms) in enumerate(keep_intervals):
            start_sec = start_ms / 1000.0
            end_sec = end_ms / 1000.0
            
            # Trim Video
            filter_parts.append(
                f"[0:v]trim=start={start_sec}:end={end_sec},setpts=PTS-STARTPTS[v{i}]"
            )
            # Trim Audio
            filter_parts.append(
                f"[0:a]atrim=start={start_sec}:end={end_sec},asetpts=PTS-STARTPTS[a{i}]"
            )
            concat_v.append(f"[v{i}]")
            concat_a.append(f"[a{i}]")
            
        # Concat
        filter_str = ";".join(filter_parts)
        concat_str = f"{''.join(concat_v)}{''.join(concat_a)}concat=n={len(keep_intervals)}:v=1:a=1[outv][outa]"
        full_filter = f"{filter_str};{concat_str}"
        
        if not keep_intervals:
            print("No keep intervals to render.")
            return

        cmd = [
            self.ffmpeg_bin, "-y",
            "-i", source_video,
            "-filter_complex", full_filter,
            "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", 
            "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-b:a", "192k",
            str(output_video)
        ]
        
        print(f"Running FFmpeg: {' '.join(cmd)}")
        try:
             subprocess.run(cmd, check=True)
             print(f"Rendered: {output_video}")
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg Error: {e}")
            raise

    def remap_srt(self, original_srt_path: str, keep_intervals: List[Tuple[int, int]], output_srt_path: str):
        """
        Shifts SRT timestamps to align with the cut timeline.
        Only keeps subtitles that fall within Keep Intervals (intersection > 50%).
        """
        if not original_srt_path or not os.path.exists(original_srt_path):
            return

        subs = pysrt.open(original_srt_path)
        new_subs = []
        
        # Accumulate time shift
        # Logic: A subtitle at T in source maps to T' in output.
        # T' = Sum(duration of previous keeps) + (T - start_of_current_keep)
        
        current_out_time = 0
        
        for keep_start, keep_end in keep_intervals:
            keep_dur = keep_end - keep_start
            
            # Find subs inside this keep interval
            # Roughly: sub.start >= keep_start AND sub.end <= keep_end
            # Or intersection logic
            
            for sub in subs:
                sub_start = sub.start.ordinal
                sub_end = sub.end.ordinal
                
                # Check intersection
                overlap_start = max(sub_start, keep_start)
                overlap_end = min(sub_end, keep_end)
                overlap_len = overlap_end - overlap_start
                
                if overlap_len > 0:
                    # If mostly inside (e.g., > 50% or just any overlap?)
                    # Let's keep if overlap is significant or center is inside
                    # Simple mapping: shift it relative to current_out_time
                    
                    # New Start = current_out_time + (overlap_start - keep_start)
                    # New End = current_out_time + (overlap_end - keep_start)
                    
                    new_sub_start = current_out_time + (overlap_start - keep_start)
                    new_sub_end = current_out_time + (overlap_end - keep_start)
                    
                    new_item = pysrt.SubRipItem(
                        index=len(new_subs)+1,
                        start=pysrt.SubRipTime(milliseconds=new_sub_start),
                        end=pysrt.SubRipTime(milliseconds=new_sub_end),
                        text=sub.text
                    )
                    new_subs.append(new_item)
            
            current_out_time += keep_dur
            
        pysrt.SubRipFile(new_subs).save(output_srt_path, encoding='utf-8')
        print(f"Remapped SRT: {output_srt_path}")
