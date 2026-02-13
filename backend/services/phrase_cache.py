"""
Pre-cached Common Phrases for Ultra-Low Latency First Response
Generates and caches TTS audio for common phrases at startup.
When AI response starts with a cached phrase, we play it instantly (~0ms)
while generating the rest of the response.
"""
import fal_client
import base64
import os
import json
import time
import asyncio
from pathlib import Path

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "audio_cache")

# ── Phrases to pre-cache ──────────────────────────────────────
# Longer phrases = more time saved while TTS generates the rest
COMMON_PHRASES = {
    "hosgeldiniz": "Hoş geldiniz! Size nasıl yardımcı olabilirim?",
    "peki_hemen": "Peki, hemen halledelim!",
    "anladim_bakayim": "Anladım, bir bakayım sizin için.",
    "tabii_ki": "Tabii ki, hemen önerebileceğim güzel seçenekler var.",
    "bir_dakika": "Bir dakika lütfen, menüye bakıyorum.",
    "guzel_secim": "Güzel bir seçim! Hemen ekliyorum.",
    "tabi_ekliyorum": "Tabii, hemen sepetinize ekliyorum!",
    "bakalim_neler": "Bakalım sizin için neler var.",
}

# Map of phrase text (lowercase, stripped) → cache key
_phrase_lookup: dict[str, str] = {}
# Map of cache key → PCM bytes
_phrase_cache: dict[str, bytes] = {}


def _build_lookup():
    """Build reverse lookup from phrase text → cache key."""
    global _phrase_lookup
    _phrase_lookup = {}
    for key, text in COMMON_PHRASES.items():
        _phrase_lookup[text.lower().strip()] = key


def match_cached_phrase(spoken_response: str) -> tuple[str | None, bytes | None, str | None]:
    """
    Check if spoken_response STARTS with a cached phrase.
    Returns (matched_phrase_text, pcm_audio_bytes, remaining_text) or (None, None, None).
    """
    if not spoken_response:
        return None, None, None

    lower = spoken_response.lower().strip()
    for text, key in _phrase_lookup.items():
        if lower.startswith(text):
            audio = _phrase_cache.get(key)
            if audio:
                remaining = spoken_response[len(text):].strip()
                return COMMON_PHRASES[key], audio, remaining
    return None, None, None


def _generate_phrase_audio(text: str) -> bytes | None:
    """Generate TTS audio for a phrase and return raw PCM bytes."""
    try:
        all_pcm = bytearray()
        stream = fal_client.stream(
            "freya-mypsdi253hbk/freya-tts",
            arguments={
                "input": text,
                "voice": "zeynep",
                "speed": 1.0,
            },
            path="/stream"
        )
        for event in stream:
            if "audio" in event:
                pcm = base64.b64decode(event["audio"])
                all_pcm.extend(pcm)
            if event.get("done"):
                break
        return bytes(all_pcm) if all_pcm else None
    except Exception as e:
        print(f"❌ Phrase cache error for '{text[:30]}': {e}")
        return None


def _save_cache(key: str, pcm_bytes: bytes):
    """Save PCM bytes to disk cache."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{key}.pcm")
    with open(path, "wb") as f:
        f.write(pcm_bytes)


def _load_cache(key: str) -> bytes | None:
    """Load PCM bytes from disk cache."""
    path = os.path.join(CACHE_DIR, f"{key}.pcm")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, "rb") as f:
            return f.read()
    return None


def load_or_generate_all():
    """
    Load cached phrases from disk, generate missing ones.
    Called at startup. Returns number of cached phrases.
    """
    _build_lookup()
    os.makedirs(CACHE_DIR, exist_ok=True)
    count = 0
    total_start = time.time()

    for key, text in COMMON_PHRASES.items():
        # Try disk cache first
        pcm = _load_cache(key)
        if pcm:
            _phrase_cache[key] = pcm
            count += 1
            duration_sec = len(pcm) / (16000 * 2)  # 16kHz, 16-bit
            print(f"  📦 Loaded '{key}' from cache ({len(pcm)} bytes, {duration_sec:.1f}s audio)")
            continue

        # Generate fresh
        start = time.time()
        pcm = _generate_phrase_audio(text)
        elapsed = time.time() - start
        if pcm:
            _phrase_cache[key] = pcm
            _save_cache(key, pcm)
            count += 1
            duration_sec = len(pcm) / (16000 * 2)
            print(f"  🔊 Generated '{key}' ({len(pcm)} bytes, {duration_sec:.1f}s audio) in {elapsed:.1f}s")
        else:
            print(f"  ⚠️ Failed to generate '{key}'")

    total = time.time() - total_start
    print(f"✅ Phrase cache ready: {count}/{len(COMMON_PHRASES)} phrases ({total:.1f}s)")
    return count


def get_cached_phrase_audio(key: str) -> bytes | None:
    """Get PCM audio for a phrase by cache key."""
    return _phrase_cache.get(key)


def get_phrase_count() -> int:
    return len(_phrase_cache)
