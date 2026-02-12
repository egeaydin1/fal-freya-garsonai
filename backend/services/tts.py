import fal_client
from core.config import get_settings
from core.fal_client_pool import get_async_http_client
import asyncio
from typing import AsyncGenerator
import os
import time
import base64

settings = get_settings()

# Set FAL API key for fal_client
os.environ['FAL_KEY'] = settings.FAL_KEY

class TTSService:
    def __init__(self):
        self.model = "freya-mypsdi253hbk/freya-tts"
        # Use pooled HTTP client instead of creating new one
        self.http_client = get_async_http_client()
        
    async def speak_stream(self, text: str, start_time: float = None) -> AsyncGenerator[bytes, None]:
        """
        Convert text to speech using Freya TTS STREAMING
        Returns PCM16 audio chunks as they are generated (real-time)
        """
        chunk_count = 0
        total_bytes = 0
        first_chunk_time = None
        
        try:
            print(f"🔊 TTS Streaming: {text[:50]}...")
            
            # Use streaming endpoint for real-time audio
            stream = fal_client.stream(
                self.model,
                arguments={
                    "input": text,
                    "voice": "zeynep",  # Turkish voice
                    "speed": 1.15       # 15% faster for reduced latency
                },
                path="/stream"  # ⚡ STREAMING MODE!
            )
            
            for event in stream:
                # Audio chunk received
                if "audio" in event:
                    chunk_count += 1
                    
                    # Decode base64 PCM data
                    audio_b64 = event["audio"]
                    pcm_bytes = base64.b64decode(audio_b64)
                    
                    total_bytes += len(pcm_bytes)
                    
                    # Log first chunk timing
                    if chunk_count == 1 and start_time:
                        first_chunk_time = time.time() - start_time
                        print(f"⚡ [First TTS chunk]: {first_chunk_time:06.3f}s (chunk size: {len(pcm_bytes)} bytes)")
                    
                    # Yield immediately to WebSocket
                    yield pcm_bytes
                
                # Error handling
                if "error" in event:
                    error = event["error"]
                    if not event.get("recoverable", False):
                        print(f"❌ TTS error: {error}")
                        raise RuntimeError(f"TTS error: {error}")
                    else:
                        print(f"⚠️ TTS recoverable error: {error}")
                
                # Stream complete
                if event.get("done"):
                    metadata = {
                        "inference_time_ms": event.get("inference_time_ms"),
                        "audio_duration_sec": event.get("audio_duration_sec")
                    }
                    
                    if start_time:
                        elapsed = time.time() - start_time
                        print(f"✅ TTS Streaming complete: {chunk_count} chunks, {total_bytes} bytes, {elapsed:06.3f}s total")
                        print(f"   Metadata: {metadata}")
                    break
            
        except Exception as e:
            print(f"❌ TTS Streaming error: {e}")
            import traceback
            traceback.print_exc()
            raise
