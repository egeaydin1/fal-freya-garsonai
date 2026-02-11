import fal_client
from core.config import get_settings
from core.fal_client_pool import get_async_http_client
import asyncio
from typing import AsyncGenerator
import os
import time

settings = get_settings()

# Set FAL API key for fal_client
os.environ['FAL_KEY'] = settings.FAL_KEY

class TTSService:
    def __init__(self):
        self.model = "freya-mypsdi253hbk/freya-tts/generate"
        # Use pooled HTTP client instead of creating new one
        self.http_client = get_async_http_client()
        
    async def speak_stream(self, text: str, start_time: float = None) -> AsyncGenerator[bytes, None]:
        """
        Convert text to speech using Freya TTS and stream audio
        """
        try:
            print(f"🔊 TTS: Generating speech for: {text[:50]}...")
            
            result = await asyncio.to_thread(
                fal_client.subscribe,
                self.model,
                arguments={
                    "input": text,
                    "voice": "zeynep",  # Turkish voice
                    "response_format": "mp3",
                    "speed": 1.1  # Slightly faster for reduced latency
                }
            )
            
            print(f"📊 TTS: Got result: {result}")
            
            if start_time:
                elapsed = time.time() - start_time
                print(f"[TTS inference done]: {elapsed:06.3f}s")
            
            # Download audio file and stream it
            if isinstance(result, dict) and "audio" in result:
                audio_url = result["audio"]["url"]
                print(f"🎵 TTS: Downloading audio from {audio_url}")
                
                async with self.http_client.stream("GET", audio_url) as response:
                    async for chunk in response.aiter_bytes(chunk_size=32768):  # 32KB chunks for faster download
                        if chunk:
                            yield chunk
                                
                print("✅ TTS: Audio streaming complete")
            else:
                print(f"⚠️ TTS: Unexpected result format: {result}")
                
        except Exception as e:
            print(f"❌ TTS Error: {e}")
            import traceback
            traceback.print_exc()
