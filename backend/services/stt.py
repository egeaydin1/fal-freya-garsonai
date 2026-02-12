import fal_client
from core.config import get_settings
import asyncio
from typing import AsyncGenerator
import tempfile
import os
import time
import httpx
import io

settings = get_settings()

# Set FAL API key for fal_client
os.environ['FAL_KEY'] = settings.FAL_KEY

class STTService:
    def __init__(self):
        # Using whisper-small for better latency (2-3x faster than base)
        self.model = "freya-mypsdi253hbk/freya-stt/generate"
        self.http_client = httpx.AsyncClient(timeout=60.0)
        self.api_url = "https://queue.fal.run/freya-mypsdi253hbk/freya-stt/generate"
        
    async def transcribe_stream(self, audio_data: bytes, start_time: float) -> str:
        """
        Transcribe audio using Whisper - DIRECT multipart POST (CDN bypass)
        """
        temp_file_path = None
        try:
            t0 = time.time()
            print(f"🎤 STT: Received {len(audio_data)} bytes")
            
            # 🚀 STRATEGY 1: Direct multipart/form-data POST (NO CDN UPLOAD)
            try:
                print("⚡ STT: Using direct binary POST (CDN bypass)")
                
                # Create file-like object from bytes
                files = {
                    "audio": ("audio.webm", io.BytesIO(audio_data), "audio/webm")
                }
                
                data = {
                    "task": "transcribe",
                    "language": "tr",
                    "chunk_level": "segment"
                }
                
                headers = {
                    "Authorization": f"Key {settings.FAL_KEY}"
                }
                
                t_request = time.time()
                response = await self.http_client.post(
                    self.api_url,
                    files=files,
                    data=data,
                    headers=headers
                )
                
                t_response = time.time()
                print(f"📡 STT: HTTP request took {t_response - t_request:.3f}s")
                
                if response.status_code != 200:
                    print(f"⚠️ Direct POST failed ({response.status_code}), trying fal_client...")
                    raise Exception(f"HTTP {response.status_code}")
                
                result = response.json()
                print(f"📊 STT: Got result: {result}")
                text = self._extract_text(result)
                
                elapsed = time.time() - start_time
                request_time = time.time() - t0
                print(f"✅ [STT done]: {elapsed:06.3f}s total | {request_time:.3f}s request")
                return text
                
            except Exception as e:
                print(f"⚠️ Direct POST failed: {e}, falling back to fal_client...")
                
                # FALLBACK: Use fal_client with file upload
                with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_file:
                    temp_file.write(audio_data)
                    temp_file_path = temp_file.name
                
                print(f"📁 STT: Created temp file {temp_file_path}")
                
                t_upload = time.time()
                print("⬆️ STT: Uploading to CDN...")
                audio_url = fal_client.upload_file(temp_file_path)
                upload_time = time.time() - t_upload
                print(f"✅ STT: Uploaded to {audio_url} ({upload_time:.3f}s)")
                
                t_inference = time.time()
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
                inference_time = time.time() - t_inference
                
                print(f"📊 STT: Got result: {result}")
                text = self._extract_text(result)
                
                elapsed = time.time() - start_time
                print(f"✅ [STT done]: {elapsed:06.3f}s total | upload: {upload_time:.3f}s | inference: {inference_time:.3f}s")
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
