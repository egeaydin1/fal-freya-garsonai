#!/usr/bin/env python3
"""
GarsonAI Voice Pipeline - Terminal Test Script

Full voice conversation loop with detailed per-stage latency logging.
Implements: LISTENING → RECORDING → TRIMMING → TRANSCRIBING → THINKING →
            CHUNKING → GENERATING → PLAYING → (back to LISTENING)

Usage:
    python voice_pipeline.py
    python voice_pipeline.py --vad-threshold 400 --silence-duration 1.0
    python voice_pipeline.py --trim-threshold 200 --trim-padding 0.2
"""

import argparse
import io
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
import wave

import numpy as np
import pyaudio
import requests
import fal_client
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# ═══════════════════════════════════════════════════════════════════
#  ANSI Colors & Logging
# ═══════════════════════════════════════════════════════════════════

class Colors:
    LISTENING    = "\033[94m"   # blue
    RECORDING    = "\033[91m"   # red
    TRIMMING     = "\033[93m"   # yellow
    TRANSCRIBING = "\033[96m"   # cyan
    THINKING     = "\033[95m"   # magenta
    CHUNKING     = "\033[33m"   # dark yellow
    GENERATING   = "\033[92m"   # green
    PLAYING      = "\033[97m"   # bright white
    CACHING      = "\033[36m"   # teal
    PIPELINE     = "\033[97m"   # bright white
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"


def log(stage: str, msg: str, duration_ms: float = None):
    """Print a timestamped, color-coded log line."""
    color = getattr(Colors, stage.upper(), Colors.RESET)
    ts = time.strftime("%H:%M:%S")
    dur = f"  ({duration_ms:,.0f}ms)" if duration_ms is not None else ""
    print(
        f"{Colors.DIM}{ts}{Colors.RESET} "
        f"{color}{Colors.BOLD}[{stage.upper():^13}]{Colors.RESET} "
        f"{msg}"
        f"{Colors.BOLD}{dur}{Colors.RESET}"
    )


# ═══════════════════════════════════════════════════════════════════
#  Audio Utilities
# ═══════════════════════════════════════════════════════════════════

def rms(data: bytes) -> float:
    """Calculate RMS energy of raw PCM16 audio bytes."""
    if len(data) < 2:
        return 0.0
    samples = np.frombuffer(data, dtype=np.int16).astype(np.float64)
    return float(np.sqrt(np.mean(samples ** 2)))


def trim_silence(frames: list, sample_rate: int, chunk_size: int,
                 threshold: float, padding_sec: float) -> list:
    """
    Remove leading/trailing silence from recorded frames.
    Keeps `padding_sec` seconds of buffer around detected speech.
    """
    energies = [rms(f) for f in frames]

    first_voice = None
    last_voice = None
    for i, e in enumerate(energies):
        if e > threshold:
            if first_voice is None:
                first_voice = i
            last_voice = i

    if first_voice is None:
        return []  # all silence

    padding_frames = int(padding_sec * sample_rate / chunk_size)
    start = max(0, first_voice - padding_frames)
    end = min(len(frames), last_voice + padding_frames + 1)

    return frames[start:end]


def frames_to_wav_bytes(frames: list, sample_rate: int, channels: int) -> bytes:
    """Pack raw PCM16 frames into a WAV byte buffer."""
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)   # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(b''.join(frames))
    return buf.getvalue()


def save_temp_wav(wav_bytes: bytes) -> str:
    """Write WAV bytes to a temp file, return the path."""
    fd, path = tempfile.mkstemp(suffix='.wav')
    with os.fdopen(fd, 'wb') as f:
        f.write(wav_bytes)
    return path


# ═══════════════════════════════════════════════════════════════════
#  Common Phrases — pre-cached for instant first-audio playback
# ═══════════════════════════════════════════════════════════════════

COMMON_PHRASES = [
    "Hoş geldiniz, size nasıl yardımcı olabilirim?",
    "Peki, hemen ilgileniyorum.",
    "Anladım, bir bakayım hemen.",
    "Tabii ki, hemen organize edeyim.",
    "Bir dakika lütfen, kontrol ediyorum.",
    "Harika, çok güzel bir tercih.",
    "Elbette, hemen halledeyim.",
    "Merhaba, hoş geldiniz efendim.",
    "Tamamdır, hemen not alıyorum.",
    "Güzel seçim, çok beğeneceksiniz.",
]

# { normalized_phrase: local_file_path }  — populated at startup
_phrase_cache: dict[str, str] = {}

CACHE_DIR = os.path.join(os.path.dirname(__file__), ".phrase_cache")


def _normalize(text: str) -> str:
    """Lowercase + strip punctuation for fuzzy cache lookup."""
    return re.sub(r'[^\w\s]', '', text.strip().lower())


def _ext_from_url(url: str) -> str:
    """Detect audio extension from URL (default .wav)."""
    for ext in ('.mp3', '.ogg', '.aac', '.flac'):
        if ext in url:
            return ext
    return '.wav'


def warm_phrase_cache():
    """
    Generate TTS for every COMMON_PHRASE and save to disk.
    Skips phrases already cached.  Called once at pipeline startup.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    log("caching", f"warming phrase cache ({len(COMMON_PHRASES)} phrases)...")

    for phrase in COMMON_PHRASES:
        key = _normalize(phrase)

        # Check if a valid cache file already exists (any extension)
        existing = None
        for ext in ('.wav', '.mp3', '.ogg', '.aac', '.flac'):
            p = os.path.join(CACHE_DIR, f"{key}{ext}")
            if os.path.exists(p) and os.path.getsize(p) > 100:
                existing = p
                break

        if existing:
            _phrase_cache[key] = existing
            log("caching", f'  ✓ cached (disk): "{phrase}"')
            continue

        # Remove any stale/broken files for this key
        for ext in ('.wav', '.mp3', '.ogg', '.aac', '.flac'):
            p = os.path.join(CACHE_DIR, f"{key}{ext}")
            if os.path.exists(p):
                os.unlink(p)

        t0 = time.perf_counter()
        try:
            tts_url = api_tts(phrase)
            resp = requests.get(tts_url, timeout=60)
            resp.raise_for_status()
            ext = _ext_from_url(tts_url)
            cached_path = os.path.join(CACHE_DIR, f"{key}{ext}")
            with open(cached_path, 'wb') as f:
                f.write(resp.content)
            _phrase_cache[key] = cached_path
            ms = (time.perf_counter() - t0) * 1000
            log("caching", f'  ✓ generated ({ext}): "{phrase}"', ms)
        except Exception as e:
            ms = (time.perf_counter() - t0) * 1000
            log("caching", f'  ✘ FAILED: "{phrase}" — {e}', ms)

    log("caching", f"{len(_phrase_cache)}/{len(COMMON_PHRASES)} phrases cached")


def lookup_phrase_cache(text: str) -> str | None:
    """Return cached audio path if `text` matches a common phrase."""
    key = _normalize(text)
    path = _phrase_cache.get(key)
    if path and os.path.exists(path):
        return path
    return None


# ═══════════════════════════════════════════════════════════════════
#  FAL API Calls  (direct fal_client — no import of existing files
#  so we avoid stt_model.py's module-level test code)
# ═══════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = (
    "You are GarsonAI, a professional voice-based restaurant assistant.\n"
    "Rules:\n"
    "- NEVER use emojis or emoticons.\n"
    "- You must keep each sentence between 6 and 7 words for optimal voice delivery speed.\n"
    " you must not repeat the same sentence.\n"
    " you must 2-3 sentences per response.\n"
    "- Respond in short, clear Turkish sentences.\n"
    "- Sound polite and natural, like a real waiter.\n"
    "- Keep responses concise — they will be spoken aloud.\n"
    "- IMPORTANT: Always start your response with one of these opening "
    "sentences (exactly as written, do not change any words): "
    + ", ".join(f'"{p}"' for p in COMMON_PHRASES) + ".\n"
    "  Pick the one that fits the context best. After this opening sentence, "
    "continue with the rest of your answer.\n"
)


def api_stt(audio_url: str) -> str:
    """Freya STT: audio URL → transcribed text."""
    result = fal_client.subscribe(
        "freya-mypsdi253hbk/freya-stt/generate",
        arguments={"audio_url": audio_url},
        with_logs=False,
    )
    # Handle various response shapes
    if isinstance(result, dict):
        return (result.get("text")
                or result.get("output")
                or result.get("transcription")
                or str(result))
    return str(result)


def api_llm(prompt: str) -> str:
    """OpenRouter LLM: prompt → response text."""
    result = fal_client.subscribe(
        "openrouter/router",
        arguments={
            "model": "google/gemini-2.5-flash-lite",
            "prompt": prompt,
            "system_prompt": SYSTEM_PROMPT,
            "temperature": 0.4,
        },
        with_logs=False,
    )
    return result["output"]


def api_tts(text: str) -> str:
    """Freya TTS: text → audio URL."""
    result = fal_client.subscribe(
        "freya-mypsdi253hbk/freya-tts/generate",
        arguments={"input": text},
        with_logs=False,
    )
    return result["audio"]["url"]


# ═══════════════════════════════════════════════════════════════════
#  Text Chunking
# ═══════════════════════════════════════════════════════════════════

def _split_leading_phrase(text: str) -> tuple[str | None, str]:
    """
    If `text` starts with a COMMON_PHRASE, split it off.
    Returns (phrase_or_None, remaining_text).
    """
    lower = text.lower()
    for phrase in sorted(COMMON_PHRASES, key=len, reverse=True):
        if lower.startswith(phrase.lower()):
            rest = text[len(phrase):].strip()
            return phrase, rest
    return None, text


def chunk_text(text: str) -> list:
    """
    Split LLM response into sentence-level chunks for streaming TTS.

    1. First, split off a leading common phrase (if any) so it can be
       played from cache instantly.
    2. Then split the remainder by sentence-ending punctuation.
    3. Falls back to comma splitting for long sentences.
    """
    text = text.strip()
    if not text:
        return [text]

    # ── Step 1: peel off cached filler phrase ──
    leading_phrase, remainder = _split_leading_phrase(text)

    # ── Step 2: split remainder by sentence enders (. ! ?) ──
    if remainder:
        parts = re.split(r'(?<=[.!?])\s+', remainder)
        parts = [p.strip() for p in parts if p.strip()]
    else:
        parts = []

    # ── Step 3: comma-split any oversized chunk ──
    expanded = []
    for p in parts:
        if len(p) > 100:
            sub = re.split(r'(?<=,)\s+', p)
            sub = [s.strip() for s in sub if s.strip()]
            expanded.extend(sub if len(sub) > 1 else [p])
        else:
            expanded.append(p)

    # ── Combine: leading phrase first, then the rest ──
    chunks = []
    if leading_phrase:
        chunks.append(leading_phrase)
    chunks.extend(expanded)

    return chunks if chunks else [text]


# ═══════════════════════════════════════════════════════════════════
#  Audio Download & Playback
# ═══════════════════════════════════════════════════════════════════

def download_audio(url: str) -> str:
    """Download audio from URL → temp file path."""
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    ext = '.wav'
    if '.mp3' in url:
        ext = '.mp3'
    elif '.ogg' in url:
        ext = '.ogg'
    fd, path = tempfile.mkstemp(suffix=ext)
    with os.fdopen(fd, 'wb') as f:
        f.write(resp.content)
    return path


def play_audio_file(path: str):
    """Play audio via macOS afplay. Blocks until done."""
    subprocess.run(["afplay", path], check=True)


# ═══════════════════════════════════════════════════════════════════
#  Main Pipeline Loop
# ═══════════════════════════════════════════════════════════════════

def run_pipeline(args):
    pa = pyaudio.PyAudio()
    FORMAT = pyaudio.paInt16
    CHUNK = int(args.sample_rate * args.poll_interval / 1000)

    # ── Banner ──
    print()
    print(f"{Colors.BOLD}{'═' * 62}{Colors.RESET}")
    print(f"{Colors.BOLD}  🎤  GarsonAI Voice Pipeline  —  Terminal Test{Colors.RESET}")
    print(f"{Colors.BOLD}{'═' * 62}{Colors.RESET}")
    print(f"  VAD threshold .... {args.vad_threshold} RMS")
    print(f"  Silence duration . {args.silence_duration}s")
    print(f"  Poll interval .... {args.poll_interval}ms  (chunk={CHUNK} frames)")
    print(f"  Trim threshold ... {args.trim_threshold} RMS")
    print(f"  Trim padding ..... {args.trim_padding}s")
    print(f"  Sample rate ...... {args.sample_rate} Hz")
    print(f"  Channels ......... {args.channels}")
    print(f"{Colors.BOLD}{'═' * 62}{Colors.RESET}")
    print(f"  Press {Colors.BOLD}Ctrl+C{Colors.RESET} to exit")
    print(f"{Colors.BOLD}{'═' * 62}{Colors.RESET}")
    print()

    # ── Warm up phrase cache ──
    warm_phrase_cache()
    print()

    turn_number = 0

    try:
        while True:

            # ════════════════════════════════════════════════════════
            #  STAGE 1 — LISTENING  (wait for voice threshold)
            # ════════════════════════════════════════════════════════
            log("listening", "waiting for voice...")

            stream = pa.open(
                format=FORMAT,
                channels=args.channels,
                rate=args.sample_rate,
                input=True,
                frames_per_buffer=CHUNK,
            )

            while True:
                data = stream.read(CHUNK, exception_on_overflow=False)
                energy = rms(data)
                if energy > args.vad_threshold:
                    break

            # ════════════════════════════════════════════════════════
            #  STAGE 2 — RECORDING  (poll every 100ms for silence)
            # ════════════════════════════════════════════════════════
            record_start = time.perf_counter()
            log("recording", f"speech detected (RMS={energy:.0f}), recording...")

            frames = [data]          # keep the first voiced chunk
            silence_start = None

            while True:
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
                energy = rms(data)

                if energy < args.vad_threshold:
                    if silence_start is None:
                        silence_start = time.perf_counter()
                    elif (time.perf_counter() - silence_start) >= args.silence_duration:
                        break
                else:
                    silence_start = None

            stream.stop_stream()
            stream.close()

            record_ms = (time.perf_counter() - record_start) * 1000
            raw_secs = len(frames) * CHUNK / args.sample_rate
            log("recording",
                f"captured {raw_secs:.1f}s ({len(frames)} chunks)",
                record_ms)

            turn_number += 1
            pipeline_start = time.perf_counter()

            # ════════════════════════════════════════════════════════
            #  STAGE 3 — TRIMMING  (strip silence from recording)
            # ════════════════════════════════════════════════════════
            t0 = time.perf_counter()
            orig_count = len(frames)
            frames = trim_silence(
                frames, args.sample_rate, CHUNK,
                args.trim_threshold, args.trim_padding,
            )
            trimmed_secs = len(frames) * CHUNK / args.sample_rate
            trim_ms = (time.perf_counter() - t0) * 1000
            log("trimming",
                f"{raw_secs:.1f}s → {trimmed_secs:.1f}s  "
                f"({orig_count}→{len(frames)} chunks)",
                trim_ms)

            if len(frames) == 0:
                log("trimming", "⚠ no speech after trimming — back to listening")
                continue

            # Convert to WAV + upload
            wav_bytes = frames_to_wav_bytes(frames, args.sample_rate, args.channels)
            wav_path = save_temp_wav(wav_bytes)

            t0 = time.perf_counter()
            audio_url = fal_client.upload_file(wav_path)
            upload_ms = (time.perf_counter() - t0) * 1000
            log("trimming",
                f"uploaded WAV ({len(wav_bytes):,} bytes) → fal",
                upload_ms)

            # ════════════════════════════════════════════════════════
            #  STAGE 4 — TRANSCRIBING  (Freya STT)
            # ════════════════════════════════════════════════════════
            t0 = time.perf_counter()
            transcript = api_stt(audio_url)
            transcribe_ms = (time.perf_counter() - t0) * 1000
            log("transcribing", f'"{transcript}"', transcribe_ms)

            if not transcript or not transcript.strip():
                log("transcribing", "⚠ empty transcript — back to listening")
                os.unlink(wav_path)
                continue

            # ════════════════════════════════════════════════════════
            #  STAGE 5 — THINKING  (LLM via OpenRouter)
            # ════════════════════════════════════════════════════════
            t0 = time.perf_counter()
            llm_response = api_llm(transcript)
            think_ms = (time.perf_counter() - t0) * 1000
            display = llm_response[:90] + ("..." if len(llm_response) > 90 else "")
            log("thinking", f'"{display}"', think_ms)

            # ════════════════════════════════════════════════════════
            #  STAGE 6 — CHUNKING  (split for streaming TTS)
            # ════════════════════════════════════════════════════════
            t0 = time.perf_counter()
            chunks = chunk_text(llm_response)
            chunk_ms = (time.perf_counter() - t0) * 1000
            log("chunking", f"{len(chunks)} chunk(s) created", chunk_ms)

            # ════════════════════════════════════════════════════════
            #  STAGE 7+8 — GENERATING + PLAYING  (parallel)
            #
            #  Producer thread: TTS each chunk → put audio path in queue
            #  Main thread:     play audio as soon as each item arrives
            #  First chunk:     check phrase cache for instant playback
            # ════════════════════════════════════════════════════════
            audio_queue = queue.Queue()   # (index, audio_path, gen_ms, label, is_cached)
            total_gen_ms = 0
            gen_ms_lock = threading.Lock()
            temp_files = []               # for cleanup later

            def tts_producer():
                """Background thread: generate TTS for each chunk."""
                nonlocal total_gen_ms
                for i, chunk in enumerate(chunks):
                    label = f"chunk {i + 1}/{len(chunks)}"
                    preview = chunk[:55] + ("..." if len(chunk) > 55 else "")

                    # ── Check phrase cache first ──
                    cached = lookup_phrase_cache(chunk)
                    if cached:
                        log("generating", f'{label}: "{preview}" ⚡ CACHED', 0)
                        audio_queue.put((i, cached, 0, label, True))
                        continue

                    # ── TTS API call ──
                    t0 = time.perf_counter()
                    try:
                        tts_url = api_tts(chunk)
                        gen_ms = (time.perf_counter() - t0) * 1000
                        with gen_ms_lock:
                            total_gen_ms += gen_ms
                        log("generating", f'{label}: "{preview}"', gen_ms)

                        t_dl = time.perf_counter()
                        audio_path = download_audio(tts_url)
                        dl_ms = (time.perf_counter() - t_dl) * 1000
                        log("generating", f"{label}: downloaded", dl_ms)
                        audio_queue.put((i, audio_path, gen_ms, label, False))
                    except Exception as e:
                        gen_ms = (time.perf_counter() - t0) * 1000
                        with gen_ms_lock:
                            total_gen_ms += gen_ms
                        log("generating", f"{label}: ✘ FAILED — {e}", gen_ms)

                audio_queue.put(None)  # sentinel: no more items

            # Start producer thread
            producer = threading.Thread(target=tts_producer, daemon=True)
            t_stage78 = time.perf_counter()
            producer.start()

            # ── Consumer (main thread): play audio as it arrives ──
            log("playing", f"streaming {len(chunks)} chunk(s) (mic disabled)...")
            play_total_ms = 0
            segments_played = 0
            first_audio_ms = None

            while True:
                item = audio_queue.get()
                if item is None:
                    break
                idx, audio_path, gen_ms, label, is_cached = item

                if first_audio_ms is None:
                    first_audio_ms = (time.perf_counter() - t_stage78) * 1000
                    src = "CACHE" if is_cached else "TTS"
                    log("playing",
                        f"⚡ first audio ready [{src}]",
                        first_audio_ms)

                t_play = time.perf_counter()
                try:
                    play_audio_file(audio_path)
                except Exception as e:
                    log("playing", f"{label}: ✘ playback error — {e}")
                play_ms = (time.perf_counter() - t_play) * 1000
                play_total_ms += play_ms
                segments_played += 1
                log("playing", f"{label} done", play_ms)

                if not is_cached:
                    temp_files.append(audio_path)

            producer.join()
            stage78_total = (time.perf_counter() - t_stage78) * 1000
            pipeline_total_ms = (time.perf_counter() - pipeline_start) * 1000

            # ── Pipeline Summary ──
            processing_ms = pipeline_total_ms - play_total_ms
            print()
            print(f"{Colors.BOLD}{'─' * 62}{Colors.RESET}")
            print(f"{Colors.BOLD}  📊  TURN #{turn_number} — PIPELINE SUMMARY{Colors.RESET}")
            print(f"{'─' * 62}")
            print(f"  Trimming ........... {trim_ms:>8,.0f} ms")
            print(f"  Upload ............. {upload_ms:>8,.0f} ms")
            print(f"  Transcribing (STT) . {transcribe_ms:>8,.0f} ms")
            print(f"  Thinking (LLM) ..... {think_ms:>8,.0f} ms")
            print(f"  Chunking ........... {chunk_ms:>8,.0f} ms")
            print(f"  Gen + Play ......... {stage78_total:>8,.0f} ms  (parallel)")
            if first_audio_ms is not None:
                print(f"  ⚡ First audio at .. {first_audio_ms:>8,.0f} ms")
            print(f"{'─' * 62}")
            print(f"  {Colors.BOLD}TOTAL PIPELINE ....... "
                  f"{pipeline_total_ms:>8,.0f} ms{Colors.RESET}")
            print(f"  {Colors.DIM}(excl. playback) .... "
                  f"{processing_ms:>8,.0f} ms{Colors.RESET}")
            print(f"{'─' * 62}")
            print()

            # Cleanup temp files (not cache files!)
            try:
                os.unlink(wav_path)
            except OSError:
                pass
            for f in temp_files:
                try:
                    os.unlink(f)
                except OSError:
                    pass

    except KeyboardInterrupt:
        print(f"\n{Colors.BOLD}GarsonAI Voice Pipeline stopped.{Colors.RESET}\n")
    finally:
        pa.terminate()


# ═══════════════════════════════════════════════════════════════════
#  CLI Entry Point
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="GarsonAI Voice Pipeline — Terminal Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python voice_pipeline.py
  python voice_pipeline.py --vad-threshold 400 --silence-duration 1.0
  python voice_pipeline.py --trim-threshold 200 --trim-padding 0.2
  python voice_pipeline.py --sample-rate 44100 --channels 1
        """,
    )

    # VAD
    parser.add_argument(
        "--vad-threshold", type=int, default=500,
        help="RMS energy above which = speech (default: 500)")
    parser.add_argument(
        "--silence-duration", type=float, default=1.5,
        help="Seconds of post-speech silence to end turn (default: 1.5)")
    parser.add_argument(
        "--poll-interval", type=int, default=100,
        help="Milliseconds between silence checks (default: 100)")

    # Trimming
    parser.add_argument(
        "--trim-threshold", type=int, default=300,
        help="RMS below which = silence to trim (default: 300)")
    parser.add_argument(
        "--trim-padding", type=float, default=0.1,
        help="Seconds of padding to keep around speech edges (default: 0.1)")

    # Audio
    parser.add_argument(
        "--sample-rate", type=int, default=16000,
        help="Mic sample rate in Hz (default: 16000)")
    parser.add_argument(
        "--channels", type=int, default=1,
        help="Mic channels — 1=mono (default: 1)")

    args = parser.parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()
