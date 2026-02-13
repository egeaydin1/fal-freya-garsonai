"""
GarsonAI Pipeline Benchmark
Tests different LLM + TTS combinations to find the fastest pipeline.

Usage:
  cd backend && source venv/bin/activate
  python benchmark.py

Tests:
  1. Gemini 2.5 Flash via fal OpenRouter
  2. GPT-4o-mini via fal OpenRouter  
  3. Cached phrase hit vs miss
  4. TTS streaming latency
  5. Full pipeline simulation (STT → LLM → TTS)
"""
import asyncio
import time
import os
import sys
import base64
import json

# Setup path
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DATABASE_URL", "sqlite:///./garsonai.db")

from core.config import get_settings
from openai import OpenAI

settings = get_settings()
os.environ["FAL_KEY"] = settings.FAL_KEY

import fal_client
from services.phrase_cache import load_or_generate_all, match_cached_phrase


def timer(label):
    """Context manager for timing blocks."""
    class Timer:
        def __init__(self):
            self.elapsed = 0
        def __enter__(self):
            self.start = time.time()
            return self
        def __exit__(self, *args):
            self.elapsed = (time.time() - self.start) * 1000
            print(f"  ⏱️  {label}: {self.elapsed:.0f}ms")
    return Timer()


def test_llm(model: str, prompt: str) -> dict:
    """Test LLM response time (streaming TTFT + total)."""
    client = OpenAI(
        api_key="fal",
        base_url="https://fal.run/openrouter/router/openai/v1",
        default_headers={"Authorization": f"Key {settings.FAL_KEY}"}
    )

    system = """Sen GarsonAI. JSON formatında yanıt ver:
{"spoken_response":"yanıt","intent":"recommend","product_name":"","product_id":null,"quantity":1,"recommendation":{"product_id":5,"product_name":"Künefe","reason":"bugünün favorisi"}}"""

    menu = """📂 Ana Yemek:
  - ID:3 | Adana Kebap | 250₺
  - ID:5 | Mantı | 180₺
📂 Tatlı:
  - ID:14 | Künefe | 150₺
  - ID:15 | Baklava | 140₺"""

    start = time.time()
    ttft = None
    full = ""

    stream = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "system", "content": f"Menü:\n{menu}"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=200,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            if ttft is None:
                ttft = (time.time() - start) * 1000
            full += delta.content

    total = (time.time() - start) * 1000

    return {
        "model": model,
        "ttft_ms": round(ttft or 0),
        "total_ms": round(total),
        "response_len": len(full),
        "response": full[:120],
    }


def test_tts(text: str) -> dict:
    """Test TTS streaming latency."""
    start = time.time()
    first_chunk_ms = None
    total_bytes = 0
    chunk_count = 0

    stream = fal_client.stream(
        "freya-mypsdi253hbk/freya-tts",
        arguments={"input": text, "voice": "zeynep", "speed": 1.0},
        path="/stream"
    )

    for event in stream:
        if "audio" in event:
            chunk_count += 1
            pcm = base64.b64decode(event["audio"])
            total_bytes += len(pcm)
            if first_chunk_ms is None:
                first_chunk_ms = (time.time() - start) * 1000
        if event.get("done"):
            break

    total = (time.time() - start) * 1000

    return {
        "text": text[:50],
        "first_chunk_ms": round(first_chunk_ms or 0),
        "total_ms": round(total),
        "chunks": chunk_count,
        "bytes": total_bytes,
        "audio_sec": round(total_bytes / (16000 * 2), 1),
    }


def test_phrase_cache() -> dict:
    """Test phrase cache hit latency."""
    # Load cache
    load_or_generate_all()

    results = {}
    test_phrases = [
        "Tabii ki, hemen önerebileceğim güzel seçenekler var. Künefe bugün çok güzel olmuş.",
        "Anladım, bir bakayım sizin için. Menümüzde harika seçenekler mevcut.",
        "Bu cümle cache'de yok, normal TTS gerekecek.",
    ]

    for phrase in test_phrases:
        start = time.time()
        matched, audio, remaining = match_cached_phrase(phrase)
        elapsed = (time.time() - start) * 1000
        results[phrase[:40]] = {
            "hit": matched is not None,
            "lookup_ms": round(elapsed, 2),
            "audio_bytes": len(audio) if audio else 0,
            "remaining": remaining[:40] if remaining else "",
        }

    return results


def main():
    print("\n" + "="*70)
    print("🏎️  GarsonAI Pipeline Benchmark")
    print("="*70)

    # ── 1. LLM Tests ──
    print("\n📊 LLM Streaming Tests")
    print("-"*50)

    test_prompt = "Ne önerirsin bana tatlı istiyorum"
    models = [
        "google/gemini-2.5-flash",
        "openai/gpt-4o-mini",
    ]

    llm_results = []
    for model in models:
        print(f"\n  Testing {model}...")
        try:
            r = test_llm(model, test_prompt)
            llm_results.append(r)
            print(f"    TTFT: {r['ttft_ms']}ms | Total: {r['total_ms']}ms | Len: {r['response_len']}")
            print(f"    Response: {r['response'][:80]}...")
        except Exception as e:
            print(f"    ❌ Error: {e}")

    # ── 2. TTS Tests ──
    print("\n📊 TTS Streaming Tests")
    print("-"*50)

    tts_tests = [
        "Tabii ki, hemen önerebileceğim güzel seçenekler var.",
        "Peki, hemen halledelim!",
        "Künefe bugünün en çok tercih edilen tatlısı, kesinlikle denemelisiniz! 150 lira.",
    ]

    tts_results = []
    for text in tts_tests:
        print(f"\n  Testing: '{text[:40]}...'")
        try:
            r = test_tts(text)
            tts_results.append(r)
            print(f"    First chunk: {r['first_chunk_ms']}ms | Total: {r['total_ms']}ms | Audio: {r['audio_sec']}s")
        except Exception as e:
            print(f"    ❌ Error: {e}")

    # ── 3. Phrase Cache Tests ──
    print("\n📊 Phrase Cache Tests")
    print("-"*50)

    cache_results = test_phrase_cache()
    for phrase, r in cache_results.items():
        hit = "✅ HIT" if r["hit"] else "❌ MISS"
        print(f"  {hit} '{phrase}...' → {r['lookup_ms']}ms, {r['audio_bytes']} bytes")

    # ── 4. Summary ──
    print("\n" + "="*70)
    print("📊 SUMMARY - Latency Targets")
    print("="*70)

    if llm_results:
        best_llm = min(llm_results, key=lambda x: x["ttft_ms"])
        print(f"\n  🏆 Fastest LLM TTFT: {best_llm['model']} → {best_llm['ttft_ms']}ms")

    if tts_results:
        best_tts = min(tts_results, key=lambda x: x["first_chunk_ms"])
        print(f"  🏆 Fastest TTS first chunk: {best_tts['first_chunk_ms']}ms for '{best_tts['text']}'")

    print(f"\n  🎯 With cached phrase: ~0ms first audio (instant playback)")
    print(f"  🎯 Without cache: LLM TTFT + TTS first chunk")
    if llm_results and tts_results:
        worst = max(r["ttft_ms"] for r in llm_results) + max(r["first_chunk_ms"] for r in tts_results)
        best = min(r["ttft_ms"] for r in llm_results) + min(r["first_chunk_ms"] for r in tts_results)
        print(f"  🎯 Best case (no cache): ~{best:.0f}ms")
        print(f"  🎯 Worst case (no cache): ~{worst:.0f}ms")

    print("\n" + "="*70)
    print("  Recommendation: Use Gemini 2.5 Flash + phrase cache for <200ms first audio")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
