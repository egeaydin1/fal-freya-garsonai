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
    def __init__(self, interval: int = 30):
        """
        Initialize TTS warmer
        
        Args:
            interval: Seconds between warm-up calls (default: 30s)
        """
        self.interval = interval
        self.model = "freya-mypsdi253hbk/freya-tts/generate"
        self.is_running = False
        self.task = None
        
    async def warmup_call(self):
        """
        Send dummy TTS request to keep container alive
        """
        try:
            start = time.time()
            
            result = await asyncio.to_thread(
                fal_client.subscribe,
                self.model,
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
    
    async def run(self):
        """
        Background task that keeps TTS warm
        """
        self.is_running = True
        print(f"🚀 TTS Warmer: Started (interval: {self.interval}s)")
        
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
            print("✅ TTS Warmer: Background task started")
    
    def stop(self):
        """
        Stop the warmer background task
        """
        self.is_running = False
        if self.task:
            self.task.cancel()
        print("🛑 TTS Warmer: Stopped")


# Global warmer instance
_warmer = None


def get_tts_warmer(interval: int = 30) -> TTSWarmer:
    """
    Get singleton TTS warmer instance
    """
    global _warmer
    if _warmer is None:
        _warmer = TTSWarmer(interval=interval)
    return _warmer


def start_tts_warmer(interval: int = 30):
    """
    Start TTS warming in background
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
