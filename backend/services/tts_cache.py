"""
TTS Sentence Cache
Pre-generates and caches audio for known starter sentences.
When the LLM response starts with a cached sentence, the cached audio
is sent immediately (~0ms latency) while the rest is synthesized in parallel.
"""
import asyncio
import fal_client
import base64
import time
import os
from typing import Optional, Dict
from core.config import get_settings

settings = get_settings()
os.environ['FAL_KEY'] = settings.FAL_KEY

# Common starter fragments — short, likely to appear in responses
CACHED_SENTENCES = [
    "Tabii, hemen sepetinize ekliyorum!",
    "Hoş geldiniz! Size nasıl yardımcı olabilirim?",
]


class TTSSentenceCache:
    """Pre-caches TTS audio for known starter sentences"""
    
    def __init__(self):
        self.model = "freya-mypsdi253hbk/freya-tts"
        self._cache: Dict[str, bytes] = {}  # sentence -> PCM16 bytes
        self._warming = False
    
    def get_cached_audio(self, spoken_response: str) -> Optional[tuple[bytes, str]]:
        """
        Check if spoken_response starts with a cached sentence.
        Returns (cached_pcm_bytes, remaining_text) or None.
        """
        for sentence in CACHED_SENTENCES:
            if spoken_response.startswith(sentence) and sentence in self._cache:
                remaining = spoken_response[len(sentence):].strip()
                return self._cache[sentence], remaining
        return None
    
    async def warm_cache(self):
        """Pre-generate TTS audio for cached sentences (sequential to avoid rate-limiting)"""
        if self._warming:
            return
        self._warming = True
        
        print(f"🔥 TTS Cache: Pre-generating {len(CACHED_SENTENCES)} sentences (sequential)...")
        start = time.time()
        success = 0
        
        for sentence in CACHED_SENTENCES:
            try:
                await self._generate_and_cache(sentence)
                success += 1
            except Exception as e:
                print(f"  ⚠️ Skipping '{sentence[:30]}...': {e}")
            # Small delay between requests to avoid rate-limiting
            await asyncio.sleep(0.5)
        
        elapsed = time.time() - start
        print(f"✅ TTS Cache: {success}/{len(CACHED_SENTENCES)} sentences cached in {elapsed:.1f}s")
        self._warming = False
    
    async def _generate_and_cache(self, sentence: str):
        """Generate TTS for a single sentence and store in cache"""
        try:
            def _sync_generate():
                # Use streaming endpoint to get PCM16 chunks
                stream = fal_client.stream(
                    self.model,
                    arguments={
                        "input": sentence,
                        "voice": "zeynep",
                        "speed": 1.15
                    },
                    path="/stream"
                )
                
                pcm_chunks = []
                for event in stream:
                    if "audio" in event:
                        pcm_bytes = base64.b64decode(event["audio"])
                        pcm_chunks.append(pcm_bytes)
                    if event.get("done"):
                        break
                
                return b"".join(pcm_chunks)
            
            pcm_data = await asyncio.to_thread(_sync_generate)
            
            if pcm_data:
                self._cache[sentence] = pcm_data
                print(f"  ✅ Cached: '{sentence[:40]}...' ({len(pcm_data)} bytes)")
            
        except Exception as e:
            print(f"  ❌ Cache failed for '{sentence[:40]}...': {e}")
            raise


# Singleton
_tts_cache: Optional[TTSSentenceCache] = None

def get_tts_cache() -> TTSSentenceCache:
    global _tts_cache
    if _tts_cache is None:
        _tts_cache = TTSSentenceCache()
    return _tts_cache
