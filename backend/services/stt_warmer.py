"""
STT Container Warm-up Service
Keeps STT container warm by sending periodic minimal requests
Reduces cold-start queue time from ~2s to near-zero
"""
import asyncio
import fal_client
from core.config import get_settings
import os
import time

settings = get_settings()
os.environ['FAL_KEY'] = settings.FAL_KEY


class STTWarmer:
    def __init__(self, interval: int = 45):
        """
        Initialize STT warmer

        Args:
            interval: Seconds between warm-up calls (default: 45s)
        """
        self.interval = interval
        self.model = "freya-mypsdi253hbk/freya-stt/generate"
        self.is_running = False
        self.task = None

    async def warmup_call(self):
        """
        Send minimal STT request to keep container alive.
        Uses a tiny silent audio buffer to trigger container spin-up.
        """
        try:
            start = time.time()

            # Create minimal valid WebM/Opus audio (silent, ~100ms)
            # This is just enough to trigger the container without real processing
            silent_audio = b'\x00' * 2000  # Minimal buffer

            # Upload and subscribe — just to keep container warm
            audio_url = await asyncio.to_thread(
                fal_client.upload, silent_audio, "audio/webm", file_name="warmup.webm"
            )

            await asyncio.to_thread(
                fal_client.subscribe,
                self.model,
                arguments={
                    "audio_url": audio_url,
                    "task": "transcribe",
                    "language": "tr",
                    "chunk_level": "segment"
                }
            )

            elapsed = time.time() - start
            print(f"🔥 STT Warmer: Keep-alive successful ({elapsed:.2f}s)")

        except Exception as e:
            # Warmup errors are expected (silent audio may fail STT)
            # The point is just to keep the container running
            elapsed = time.time() - start
            print(f"🔥 STT Warmer: Ping sent ({elapsed:.2f}s) — {type(e).__name__}")

    async def run(self):
        """Background task that keeps STT warm"""
        self.is_running = True
        print(f"🚀 STT Warmer: Started (interval: {self.interval}s)")

        # Initial warmup after short delay
        await asyncio.sleep(5)
        await self.warmup_call()

        while self.is_running:
            await asyncio.sleep(self.interval)
            if self.is_running:
                await self.warmup_call()

    def start(self):
        """Start the warmer background task"""
        if not self.task or self.task.done():
            self.task = asyncio.create_task(self.run())
            print("✅ STT Warmer: Background task started")

    def stop(self):
        """Stop the warmer background task"""
        self.is_running = False
        if self.task:
            self.task.cancel()
        print("🛑 STT Warmer: Stopped")


# Global warmer instance
_warmer = None


def get_stt_warmer(interval: int = 45) -> STTWarmer:
    """Get singleton STT warmer instance"""
    global _warmer
    if _warmer is None:
        _warmer = STTWarmer(interval=interval)
    return _warmer


def start_stt_warmer(interval: int = 45):
    """Start STT warming in background"""
    warmer = get_stt_warmer(interval)
    warmer.start()
    return warmer


def stop_stt_warmer():
    """Stop STT warming"""
    global _warmer
    if _warmer:
        _warmer.stop()
