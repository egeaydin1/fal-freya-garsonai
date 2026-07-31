"""
TTS Container Warm-up Service
Keeps TTS container warm by sending periodic dummy requests
Reduces queue time from ~2s to near-zero
"""
import asyncio
import fal_client
from core.config import get_settings
import os
import time

settings = get_settings()
os.environ['FAL_KEY'] = settings.FAL_KEY


class TTSWarmer:
    def __init__(self, interval: int = 20):
        """
        Initialize TTS warmer
        
        Args:
            interval: Seconds between warm-up calls (default: 20s - aggressive)
        """
        self.interval = interval
        self.tts_model = "freya-mypsdi253hbk/freya-tts/generate"
        self.stt_model = "freya-mypsdi253hbk/freya-stt/generate"
        self.is_running = False
        self.task = None
        
    async def warmup_tts(self):
        """
        Send dummy TTS request to keep container alive
        """
        try:
            start = time.time()
            
            result = await asyncio.to_thread(
                fal_client.subscribe,
                self.tts_model,
                arguments={
                    "input": "test",  # Minimal input
                    "voice": "zeynep",
                    "response_format": "mp3",
                    "speed": 1.15
                }
            )
            
            elapsed = time.time() - start
            print(f"🔥 TTS Warmer: Keep-alive successful ({elapsed:.2f}s)")
            
        except Exception as e:
            print(f"⚠️ TTS Warmer: Error during warm-up: {e}")
    
    async def warmup_stt(self):
        """
        Send dummy STT request to keep Whisper container alive
        Reduces cold start from 2-3s to near-zero
        """
        try:
            start = time.time()
            
            # Minimal silent audio (1 second)
            import base64
            # 1 second of silence in base64 (minimal payload)
            silent_audio = base64.b64encode(b'\x00' * 1000).decode('utf-8')
            
            result = await asyncio.to_thread(
                fal_client.subscribe,
                self.stt_model,
                arguments={
                    "audio": silent_audio,
                    "task": "transcribe",
                    "language": "tr"
                }
            )
            
            elapsed = time.time() - start
            print(f"🔥 STT Warmer: Keep-alive successful ({elapsed:.2f}s)")
            
        except Exception as e:
            print(f"⚠️ STT Warmer: Error during warm-up: {e}")
    
    async def run(self):
        """
        Background task that keeps TTS and STT warm
        """
        self.is_running = True
        print(f"🚀 Container Warmer: Started (interval: {self.interval}s)")
        
        while self.is_running:
            await asyncio.sleep(self.interval)
            
            if self.is_running:  # Check again after sleep
                # Warm both containers in parallel
                await asyncio.gather(
                    self.warmup_tts(),
                    self.warmup_stt(),
                    return_exceptions=True
                )
    
    def start(self):
        """
        Start the warmer background task
        """
        if not self.task or self.task.done():
            self.task = asyncio.create_task(self.run())
            print("✅ Container Warmer: Background task started (TTS + STT)")
    
    def stop(self):
        """
        Stop the warmer background task
        """
        self.is_running = False
        if self.task:
            self.task.cancel()
        print("🛑 Container Warmer: Stopped")


# Global warmer instance
_warmer = None


def get_tts_warmer(interval: int = 20) -> TTSWarmer:
    """
    Get singleton TTS warmer instance
    """
    global _warmer
    if _warmer is None:
        _warmer = TTSWarmer(interval=interval)
    return _warmer


def start_tts_warmer(interval: int = 20):
    """
    Start TTS + STT warming in background (aggressive 20s interval)
    """
    warmer = get_tts_warmer(interval)
    warmer.start()
    return warmer


def stop_tts_warmer():
    """
    Stop TTS warming
    """
    global _warmer
    if _warmer:
        _warmer.stop()
