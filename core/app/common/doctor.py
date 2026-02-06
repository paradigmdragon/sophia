import shutil
import requests
import logging
from app.common.utils import get_logger

logger = get_logger("Doctor")

class Doctor:
    def check_ffmpeg(self) -> bool:
        """Check if ffmpeg is installed."""
        if shutil.which("ffmpeg"):
            logger.info("ffmpeg: OK")
            return True
        else:
            logger.error("ffmpeg: NOT FOUND. Please install ffmpeg.")
            return False

    def check_ollama(self) -> bool:
        """Check if ollama is running."""
        # Check binary first
        if not shutil.which("ollama"):
            logger.info("ollama binary: NOT FOUND (Optional)")
            return False
            
        # Check server
        try:
            response = requests.get("http://127.0.0.1:11434/api/tags", timeout=1)
            if response.status_code == 200:
                logger.info("ollama server: OK")
                return True
        except requests.ConnectionError:
            pass
        except Exception as e:
             logger.warning(f"ollama server check failed: {e}")

        logger.info("ollama server: NOT RUNNING (Optional)")
        return False

    def check_environment(self) -> bool:
        """Run all checks."""
        ffmpeg_ok = self.check_ffmpeg()
        self.check_ollama() # Optional, result ignored for overall success
        
        return ffmpeg_ok
