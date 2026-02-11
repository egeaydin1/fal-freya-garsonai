import fal_client
from core.config import get_settings
import asyncio
from typing import AsyncGenerator

settings = get_settings()

class STTService:
    def __init__(self):
        self.model = "freya-mypsdi253hbk/freya-stt/models"
        
    async def transcribe_stream(self, audio_data: bytes) -> str:
        """
        Transcribe audio using Freya STT
        """
        try:
            # Upload audio file
            audio_url = fal_client.upload_file(audio_data)
            
            # Call STT model
            result = await asyncio.to_thread(
                fal_client.subscribe,
                self.model,
                arguments={
                    "audio_url": audio_url,
                    "model": "freya-stt-v1",
                    "response_format": "json"
                }
            )
            
            # Extract transcription
            if isinstance(result, dict) and "text" in result:
                return result["text"]
            return ""
            
        except Exception as e:
            print(f"STT Error: {e}")
            return ""
