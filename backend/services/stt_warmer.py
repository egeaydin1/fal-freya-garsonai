"""
STT Container Warm-up Service
Keeps STT container warm by sending periodic dummy requests
Reduces queue time from ~2s to near-zero
"""
import asyncio
import fal_client
from core.config import get_settings
import os
import time
import tempfile

settings = get_settings()
os.environ['FAL_KEY'] = settings.FAL_KEY


class STTWarmer:
    def __init__(self, interval: int = 30):
        """
        Initialize STT warmer
        
        Args:
            interval: Seconds between warm-up calls (default: 30s)
        """
        self.interval = interval
        self.model = "freya-mypsdi253hbk/freya-stt/generate"
        self.is_running = False
        self.task = None
        
    async def warmup_call(self):
        """
        Send dummy STT request to keep container alive
        Uses minimal silent audio
        """
        try:
            start = time.time()
            
            # Create tiny silent audio (0.5s WebM)
            # This is just a warm-up, actual content doesn't matter
            dummy_audio = b'\x1a\x45\xdf\xa3'  # Minimal WebM header
            
            # Upload dummy audio
            with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_file:
                temp_file.write(dummy_audio)
                temp_file_path = temp_file.name
            
            try:
                audio_url = fal_client.upload_file(temp_file_path)
                
                result = await asyncio.to_thread(
                    fal_client.subscribe,
                    self.model,
                    arguments={
                        "audio_url": audio_url,
                        "task": "transcribe",
                        "language": "tr"
                    }
                )
                
                elapsed = time.time() - start
                print(f"🔥 STT Warmer: Keep-alive successful ({elapsed:.2f}s)")
                
            finally:
                # Cleanup temp file
                os.unlink(temp_file_path)
            
        except Exception as e:
            print(f"⚠️ STT Warmer: Error during warm-up: {e}")
    
    async def run(self):
        """
        Background task that keeps STT warm
        """
        self.is_running = True
        print(f"🚀 STT Warmer: Started (interval: {self.interval}s)")
        
        while self.is_running:
            await asyncio.sleep(self.interval)
            
            if self.is_running:  # Check again after sleep
                await self.warmup_call()
    
    def start(self):
        """
        Start the warmer background task
        """
        if not self.task or self.task.done():
            self.task = asyncio.create_task(self.run())
            print("✅ STT Warmer: Background task started")
    
    def stop(self):
        """
        Stop the warmer background task
        """
        self.is_running = False
        if self.task:
            self.task.cancel()
        print("🛑 STT Warmer: Stopped")


# Global warmer instance
_warmer = None


def get_stt_warmer(interval: int = 30) -> STTWarmer:
    """
    Get singleton STT warmer instance
    """
    global _warmer
    if _warmer is None:
        _warmer = STTWarmer(interval=interval)
    return _warmer


def start_stt_warmer(interval: int = 30):
    """
    Start STT warming in background
    """
    warmer = get_stt_warmer(interval)
    warmer.start()
    return warmer


def stop_stt_warmer():
    """
    Stop STT warming
    """
    global _warmer
    if _warmer:
        _warmer.stop()
