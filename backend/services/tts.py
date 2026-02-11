import fal_client
from core.config import get_settings
import asyncio
from typing import AsyncGenerator

settings = get_settings()

class TTSService:
    def __init__(self):
        self.model = "freya-mypsdi253hbk/freya-tts/models"
        
    async def speak_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Convert text to speech using Freya TTS
        Stream audio chunks immediately
        """
        try:
            result = await asyncio.to_thread(
                fal_client.subscribe,
                self.model,
                arguments={
                    "input": text,
                    "voice": "zeynep",
                    "response_format": "wav",
                    "speed": 1
                }
            )
            
            # Get audio URL
            if isinstance(result, dict) and "audio_url" in result:
                audio_url = result["audio_url"]
                
                # Download and stream chunks
                import httpx
                async with httpx.AsyncClient() as client:
                    async with client.stream("GET", audio_url) as response:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            yield chunk
            
        except Exception as e:
            print(f"TTS Error: {e}")
            yield b""
