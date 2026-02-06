import os
import shutil
import time
from typing import List, Optional
from app.config import ConfigLoader
from app.common.utils import get_logger, calculate_file_hash
from app.events.emitter import emit_event
from app.common.doctor import Doctor
from app.asr.whisper_engine import ASREngine
from app.refine.refiner import Refiner
from app.common.writer import Writer

logger = get_logger("Pipeline")

class Pipeline:
    def __init__(self, output_dir: str = None, config_path: Optional[str] = None):
        if config_path:
            self.config = ConfigLoader(config_path).load()
        else:
            self.config = ConfigLoader().load()
            
        self.doctor = Doctor()
        self.engine = ASREngine()
        self.refiner = Refiner()
        self.writer = Writer()
        
        # Paths
        self.outbox = output_dir if output_dir else "outbox"
        self.logs = "logs" # Keep logs in project dir or could be redirected? For now keep simple.
        
        # Create output dir if not exists
        if not os.path.exists(self.outbox):
             os.makedirs(self.outbox, exist_ok=True)

    def run(self, files: List[str]):
        logger.info("Starting Sophia Pipeline (v0.1.2)...")
        # emit_event("run_start", {"file_count": len(files)})
        
        # 1. Doctor Check
        self.doctor.check_environment()
        
        if not files:
            logger.info("No files provided.")
            emit_event("run_done", {"status": "no_files"})
            return

        logger.info(f"Processing {len(files)} files.")
        
        # 3. Process Loop
        for file_path in files:
            self.process_file(file_path)
        
        emit_event("run_done")

    def process_file(self, file_path: str):
        filename = os.path.basename(file_path)
        emit_event("file_start", {"file": filename})
        # logger.info(f"Processing: {filename}")
        
        start_time = time.time()
        
        try:
            # Hash
            if os.path.exists(file_path):
                file_hash = calculate_file_hash(file_path)
            else:
                 raise FileNotFoundError(f"File not found: {file_path}")

            # ASR
            # Mock progress for now or hook into whisper callback if possible (future)
            emit_event("progress", {"file": filename, "sec": 0.0, "status": "loading_model"})
            
            logger.info("Calling engine.transcribe...")
            emit_event("log", {"message": f"Starting transcription for {filename}..."})
            
            # This call might take time if loading model or inferencing
            segments, info = self.engine.transcribe(file_path, config=self.config)
            
            segment_count = len(segments)
            logger.info(f"Transcribed {segment_count} segments. Language: {info.language}")
            emit_event("log", {"message": f"Inference complete. Segments: {segment_count}, Lang: {info.language}"})
            
            # Prepare Outputs
            base_name = os.path.splitext(filename)[0]
            srt_path = os.path.join(self.outbox, f"{base_name}.sub.srt") # Changed to .sub.srt to differentiate? Or keep raw.srt? User said 'raw.srt' in task. Let's keep raw.srt but ensure path is correct.
            # Using raw.srt as per original code
            srt_path = os.path.join(self.outbox, f"{base_name}.raw.srt")
            txt_path = os.path.join(self.outbox, f"{base_name}.txt")
            log_path = os.path.join(self.outbox, f"{base_name}.run.json") 
            
            emit_event("log", {"message": f"Writing output files to {self.outbox}..."})
            
            # Write
            self.writer.write_srt(segments, srt_path)
            self.writer.write_txt(segments, txt_path)
            
            emit_event("log", {"message": "Files written successfully."})
            
            # Log Data
            duration = time.time() - start_time
            log_data = {
                "file": filename,
                "hash": file_hash,
                "engine": self.config["engine"]["type"],
                "model": self.config["engine"].get("model_size", "medium"),
                "language": info.language,
                "duration_total_sec": round(duration, 2),
                "media_duration_sec": info.duration,
                "status": "success",
                "ollama_available": self.doctor.check_ollama()
            }
            self.writer.write_log(log_data, log_path)
            
            # --- Refinement Step ---
            emit_event("refine_started", {"file": filename})
            base_output_path = os.path.join(self.outbox, base_name)
            
            # segments is a list of Segment objects (from faster_whisper)
            # Refiner expects list of objects or dicts. 
            # Engine returns list of Segment objects.
            # Refiner implementation (v0.1.3) handles property access 
            # and conversion to dict internally in merge_segments.
            
            refine_result = self.refiner.refine(segments, base_output_path, config=self.config)
            
            emit_event("refine_completed", {
                "file": filename, 
                "outputs": refine_result
            })
            # -----------------------

            emit_event("file_done", {"file": filename, "status": "success", "output": srt_path})
            # No move to processed in this version, keep original in place

        except Exception as e:
            logger.error(f"Failed to process {filename}: {e}")
            emit_event("file_done", {"file": filename, "status": "error", "error": str(e)})
            
            # Write error log
            # error_log_path = os.path.join(self.outbox, f"{os.path.splitext(filename)[0]}.error.json")
            # error_data = {
            #     "file": filename,
            #     "error": str(e),
            #     "status": "failed"
            # }
            # self.writer.write_log(error_data, error_log_path)
