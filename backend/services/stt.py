import fal_client
from core.config import get_settings
import asyncio
from typing import AsyncGenerator
import tempfile
import os
import time

settings = get_settings()

# Set FAL API key for fal_client
os.environ['FAL_KEY'] = settings.FAL_KEY

class STTService:
    def __init__(self):
        # Using whisper-small for better latency (2-3x faster than base)
        self.model = "freya-mypsdi253hbk/freya-stt/generate"
        
    async def transcribe_stream(self, audio_data: bytes, start_time: float) -> str:
        """
        Transcribe audio using Whisper - optimized with base64 to skip upload
        """
        temp_file_path = None
        try:
            print(f"🎤 STT: Received {len(audio_data)} bytes")
            
            # Try base64 audio first (faster - no upload)
            try:
                import base64
                audio_b64 = base64.b64encode(audio_data).decode('utf-8')
                
                print("🚀 STT: Using base64 audio (no upload)")
                result = await asyncio.to_thread(
                    fal_client.subscribe,
                    self.model,
                    arguments={
                        "audio": audio_b64,
                        "task": "transcribe",
                        "language": "tr",
                        "chunk_level": "segment"
                    }
                )
                
                print(f"📊 STT: Got result: {result}")
                text = self._extract_text(result)
                elapsed = time.time() - start_time
                print(f"[STT done]: {elapsed:06.3f}s")
                return text
                
            except Exception as e:
                print(f"⚠️ Base64 failed, falling back to upload: {e}")
                
                # Fallback: Upload to CDN
                with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_file:
                    temp_file.write(audio_data)
                    temp_file_path = temp_file.name
                
                print(f"📁 STT: Created temp file {temp_file_path}")
                print("⬆️ STT: Uploading to fal.ai...")
                audio_url = fal_client.upload_file(temp_file_path)
                print(f"✅ STT: Uploaded to {audio_url}")
                
                print("🤖 STT: Calling Whisper...")
                result = await asyncio.to_thread(
                    fal_client.subscribe,
                    self.model,
                    arguments={
                        "audio_url": audio_url,
                        "task": "transcribe",
                        "language": "tr",
                        "chunk_level": "segment"
                    }
                )
                
                print(f"📊 STT: Got result: {result}")
                text = self._extract_text(result)
                elapsed = time.time() - start_time
                print(f"[STT done]: {elapsed:06.3f}s")
                return text
            
        except Exception as e:
            print(f"❌ STT Error: {e}")
            import traceback
            traceback.print_exc()
            return ""
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                print(f"🗑️ STT: Cleaned up temp file")
    
    def _extract_text(self, result) -> str:
        """Extract text from Whisper result"""
        if isinstance(result, str):
            print(f"✅ STT: Transcription successful: {result}")
            return result
        elif isinstance(result, dict):
            if "text" in result:
                print(f"✅ STT: Transcription successful: {result['text']}")
                return result["text"]
            elif "chunks" in result and len(result["chunks"]) > 0:
                text = " ".join([chunk.get("text", "") for chunk in result["chunks"]])
                print(f"✅ STT: Transcription successful: {text}")
                return text
        
        print(f"⚠️ STT: Unexpected result format: {result}")
        return ""
