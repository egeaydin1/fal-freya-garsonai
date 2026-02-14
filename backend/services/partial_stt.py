"""
Partial/Incremental STT Service
Supports real-time transcription while user is still speaking.
"""

import fal_client
import asyncio
import time
import os
from typing import Optional
from core.config import get_settings

settings = get_settings()

# Set FAL API key
os.environ['FAL_KEY'] = settings.FAL_KEY


class PartialSTTService:
    """
    Incremental Speech-to-Text service.
    
    Processes audio chunks in real-time without waiting for complete recording.
    Optimized for low-latency partial transcription.
    """
    
    def __init__(self):
        self.model = "freya-mypsdi253hbk/freya-stt/generate"
        self.last_result = ""
        self.processing_semaphore = asyncio.Semaphore(2)  # Reduced to 2 for better stability
        self.last_request_time = 0
        self.min_request_interval = 0.80  # Increased to 800ms to prevent flooding
    
    async def transcribe_partial(
        self, 
        audio_data: bytes, 
        start_time: float,
        is_final: bool = False
    ) -> dict:
        """
        Transcribe audio chunk (incremental).
        
        Args:
            audio_data: Audio bytes (WebM/Opus)
            start_time: Session start timestamp
            is_final: Whether this is the final chunk
        
        Returns:
            {
                "text": "partial transcript",
                "is_final": False,
                "confidence": 0.95,
                "processing_time": 0.456
            }
        """
        async with self.processing_semaphore:
            process_start = time.time()
            
            # Rate limiting: ensure minimum time between requests
            time_since_last = process_start - self.last_request_time
            if time_since_last < self.min_request_interval:
                wait_time = self.min_request_interval - time_since_last
                await asyncio.sleep(wait_time)
            
            self.last_request_time = time.time()
            
            try:
                # Skip very small audio chunks (< 4KB)
                # 164 bytes is definitely too small and causes container issues
                if len(audio_data) < 500:
                    print(f"⏭️ Skipping small audio chunk: {len(audio_data)} bytes")
                    return {
                        "text": "",
                        "is_final": is_final,
                        "is_incomplete": False,
                        "confidence": 0.0,
                        "processing_time": 0.0,
                        "skipped": True
                    }
                
                print(f"🎤 STT: {len(audio_data)} bytes (final={is_final})")
                
                # Upload with unique filename to prevent CDN/Cache clashing
                upload_id = f"{int(time.time())}_{len(audio_data)}"
                audio_url = await asyncio.to_thread(
                    fal_client.upload, 
                    audio_data, 
                    "audio/webm", 
                    file_name=f"audio_{upload_id}.webm"
                )
                
                # Call Freya STT with retry logic for 500 errors (FAL STT often returns 500 on result fetch)
                max_retries = 3  # 4 attempts total; FAL freya-stt can be flaky
                retry_delay = 1.5
                last_error = None
                result = None
                
                for attempt in range(max_retries + 1):
                    try:
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
                        break  # Success, exit retry loop
                    except Exception as e:
                        last_error = e
                        error_str = str(e)
                        
                        # Check if it's a 500 error (server error) — FAL STT returns this when result fetch fails
                        if "500" in error_str or "internal_server_error" in error_str.lower():
                            if attempt < max_retries:
                                wait_time = retry_delay * (2 ** attempt)
                                print(f"⚠️ STT 500 error, retrying in {wait_time:.0f}s (attempt {attempt + 1}/{max_retries + 1})")
                                await asyncio.sleep(wait_time)
                                continue
                        
                        # Not a 500 error or out of retries, raise
                        raise
                
                # If we exhausted retries, raise the last error
                if result is None and last_error is not None:
                    raise last_error
                
                text = self._extract_text(result)
                processing_time = time.time() - process_start
                
                elapsed = time.time() - start_time
                print(f"[Partial STT]: {elapsed:06.3f}s - '{text}' ({processing_time:.3f}s)")
                
                # Detect if this is likely incomplete
                is_likely_incomplete = not is_final and not text.strip().endswith((".", "!", "?"))
                
                return {
                    "text": text,
                    "is_final": is_final,
                    "is_incomplete": is_likely_incomplete,
                    "confidence": self._estimate_confidence(result),
                    "processing_time": processing_time,
                    "elapsed_time": elapsed
                }
                
            except Exception as e:
                print(f"❌ STT Error: {e}")
                import traceback
                traceback.print_exc()
                
                return {
                    "text": "",
                    "is_final": is_final,
                    "is_incomplete": False,
                    "confidence": 0.0,
                    "processing_time": time.time() - process_start,
                    "error": str(e)
                }
    
    async def transcribe_streaming(
        self,
        audio_chunks_generator,
        start_time: float
    ):
        """
        Streaming transcription (if API supports it - experimental).
        
        Yields partial results as audio arrives.
        Currently falls back to chunk-based processing.
        """
        async for chunk in audio_chunks_generator:
            result = await self.transcribe_partial(chunk, start_time, is_final=False)
            yield result
    
    def _extract_text(self, result) -> str:
        """Extract text from Whisper result."""
        if isinstance(result, str):
            return result
        elif isinstance(result, dict):
            if "text" in result:
                return result["text"]
            elif "chunks" in result and len(result["chunks"]) > 0:
                return " ".join([chunk.get("text", "") for chunk in result["chunks"]])
        return ""
    
    def _estimate_confidence(self, result) -> float:
        """
        Estimate transcription confidence.
        
        Freya STT doesn't return confidence scores directly,
        so we use heuristics based on result structure.
        """
        if isinstance(result, dict):
            # Check if chunks exist (usually means higher quality)
            if "chunks" in result and len(result["chunks"]) > 0:
                return 0.85  # Assume high confidence
            elif "text" in result and result["text"]:
                return 0.75  # Medium confidence
        elif isinstance(result, str) and result:
            return 0.75
        
        return 0.5  # Low confidence fallback
    
    def merge_transcripts(self, old: str, new: str) -> str:
        """
        Intelligently merge partial transcripts.
        
        Handles overlap and duplication from incremental processing.
        """
        if not old:
            return new
        if not new:
            return old
        
        # Simple approach: append if new text adds content
        # More sophisticated: diff-based merging
        
        # Check if new starts with end of old (overlap)
        words_old = old.split()
        words_new = new.split()
        
        # Find overlap
        max_overlap = min(len(words_old), len(words_new), 5)  # Check last 5 words
        
        for i in range(max_overlap, 0, -1):
            if words_old[-i:] == words_new[:i]:
                # Found overlap, merge
                merged = old + " " + " ".join(words_new[i:])
                return merged.strip()
        
        # No overlap, concatenate
        return (old + " " + new).strip()
