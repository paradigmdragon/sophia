from faster_whisper import WhisperModel
import logging
from typing import Tuple, List, Any
from app.config import get_config
from app.common.utils import get_logger

logger = get_logger("Engine")

class ASREngine:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ASREngine, cls).__new__(cls)
        return cls._instance

    def _load_model(self, config: dict = None):
        if config:
            conf = config
        else:
            conf = get_config()
            
        engine_conf = conf.get("engine", {})
        
        model_size = engine_conf.get("model_size", "medium")
        device = engine_conf.get("device", "auto")
        compute_type = engine_conf.get("compute_type", "float16")

        logger.info(f"Loading Whisper model: {model_size} ({device}, {compute_type})...")
        try:
            self._model = WhisperModel(model_size, device=device, compute_type=compute_type)
            logger.info("Model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise

    def transcribe(self, audio_path: str, config: dict = None) -> Tuple[List[Any], dict]:
        """
        Transcribe audio file.
        Returns (segments, info)
        """
        if self._model is None:
            self._load_model(config)
        
        if config:
            conf = config
        else:
            conf = get_config()
            
        lang = conf.get("language", "ko")
        
        logger.info(f"Transcribing {audio_path} (lang={lang})...")
        segments, info = self._model.transcribe(
            audio_path, 
            language=lang,
            beam_size=5 
        )
        
        # segments is a generator, consume it to ensure processing is done if needed right away, 
        # but faster-whisper returns a generator. 
        # For our pipeline, we might want to convert to list to avoid keeping file handle open?
        # Re-reading docs: faster-whisper segments is a generator. 
        # We will return the generator to stream processing or listify it here.
        # Given we need to write to file, listifying is safer for error handling and file moves.
        result_segments = list(segments)
        
        return result_segments, info
