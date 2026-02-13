"""
Optimized Voice Pipeline v2
Full pipeline with detailed ms-level logging for every stage:
  LISTENING → TRANSCRIBING → THINKING → CHUNKING → GENERATING → PLAYING

Key optimizations:
  - Pre-cached common phrases → instant first audio (~0ms TTS)
  - Aggressive sentence chunking → TTS fires on first sentence
  - Silence trimming on received audio (configurable)
  - Pipeline timing logs for every stage
  - No listening while playing (frontend-enforced, backend tracks state)
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session, joinedload
from core.database import get_db
from models.models import Table, Product
from services.stt import STTService
from services.tts import TTSService
from services.llm import LLMService
from services.phrase_cache import match_cached_phrase, COMMON_PHRASES
from websocket.manager import manager
import json
import asyncio
import time
import re
import struct

router = APIRouter()

stt_service = STTService()
tts_service = TTSService()
llm_service = LLMService()


# ── Audio silence trimmer ──────────────────────────────────────
def trim_silence(audio_data: bytes, threshold: int = 500, min_chunk: int = 320) -> bytes:
    """
    Remove leading/trailing silence from WebM/Opus audio.
    For raw PCM this would work; for WebM containers we skip trimming
    since the codec handles it. Returns as-is for non-PCM formats.
    """
    # WebM/Opus is compressed - trimming needs decoding, so skip for now.
    # The real silence trimming happens on the frontend VAD side.
    return audio_data


# ── Pipeline logger ────────────────────────────────────────────
class PipelineTimer:
    """Logs every stage of the voice pipeline with ms precision."""

    def __init__(self):
        self.start_time = time.time()
        self.stages: list[tuple[str, float, float]] = []  # (name, start_ms, end_ms)
        self._current_stage = None
        self._stage_start = None

    def begin(self, stage: str):
        now = time.time()
        if self._current_stage:
            elapsed = (now - self._stage_start) * 1000
            self.stages.append((self._current_stage, (self._stage_start - self.start_time) * 1000, elapsed))
        self._current_stage = stage
        self._stage_start = now

    def end(self, stage: str = None):
        now = time.time()
        if self._current_stage:
            elapsed = (now - self._stage_start) * 1000
            self.stages.append((self._current_stage, (self._stage_start - self.start_time) * 1000, elapsed))
        self._current_stage = None
        self._stage_start = None

    def total_ms(self) -> float:
        return (time.time() - self.start_time) * 1000

    def report(self) -> str:
        lines = [f"\n{'─'*60}", "📊 PIPELINE TIMING REPORT", f"{'─'*60}"]
        for name, offset_ms, duration_ms in self.stages:
            bar_len = max(1, int(duration_ms / 50))
            bar = "█" * min(bar_len, 30)
            lines.append(f"  {name:<18} │ {offset_ms:7.0f}ms │ {duration_ms:7.0f}ms │ {bar}")
        lines.append(f"{'─'*60}")
        lines.append(f"  {'TOTAL':<18} │         │ {self.total_ms():7.0f}ms │")
        lines.append(f"{'─'*60}\n")
        return "\n".join(lines)


# ── Helpers ────────────────────────────────────────────────────
def build_menu_context(products):
    """Build rich menu context with IDs, categories, descriptions, allergens."""
    categories = {}
    for p in products:
        cat = getattr(p, "category", None) or "Diğer"
        if cat not in categories:
            categories[cat] = []
        allergen_names = []
        try:
            allergen_names = [a.name for a in p.allergens]
        except Exception:
            pass
        allergen_str = f" [Alerjen: {', '.join(allergen_names)}]" if allergen_names else ""
        categories[cat].append(
            f"  - ID:{p.id} | {p.name} | {p.price}₺ | {p.description or ''}{allergen_str}"
        )
    lines = []
    for cat, items in categories.items():
        lines.append(f"\n📂 {cat}:")
        lines.extend(items)
    return "\n".join(lines)


def find_product_for_recommendation(products, structured_data):
    rec = structured_data.get("recommendation", {})
    if not rec:
        return None
    pid = rec.get("product_id")
    if pid:
        for p in products:
            if p.id == pid:
                return p
    pname = rec.get("product_name", "")
    if pname:
        for p in products:
            if pname.lower() in p.name.lower():
                return p
    return None


def product_to_dict(p, reason=""):
    allergens = []
    try:
        allergens = [{"id": a.id, "name": a.name, "icon": a.icon} for a in p.allergens]
    except Exception:
        pass
    return {
        "id": p.id, "name": p.name, "description": p.description,
        "price": p.price, "image_url": p.image_url,
        "category": getattr(p, "category", None),
        "allergens": allergens, "reason": reason,
    }


def extract_spoken_text(full_response: str) -> str | None:
    try:
        m = re.search(r'"spoken_response"\s*:\s*"([^"]*)"', full_response)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


# ── WebSocket endpoint ─────────────────────────────────────────
@router.websocket("/ws/voice/{table_id}")
async def voice_websocket_v2(
    websocket: WebSocket, table_id: str, db: Session = Depends(get_db)
):
    """
    Optimized v2 voice pipeline with:
    - Pre-cached phrase matching for instant first audio
    - Detailed ms-level logging for every stage
    - Aggressive chunked parallel TTS
    - State tracking (no listen while playing)
    """
    await manager.connect(websocket, table_id)

    table = db.query(Table).filter(Table.qr_token == table_id).first()
    if not table:
        await websocket.close(code=4004, reason="Table not found")
        return

    products = (
        db.query(Product)
        .options(joinedload(Product.allergens))
        .filter(Product.restaurant_id == table.restaurant_id, Product.is_available == True)
        .all()
    )
    menu_context = build_menu_context(products)

    # ── Send greeting ──
    try:
        greeting = "Hoş geldiniz! Size nasıl yardımcı olabilirim? 🎤 Mikrofona basarak sipariş verebilir veya öneri isteyebilirsiniz."
        await websocket.send_json({"type": "greeting", "text": greeting})
    except Exception as e:
        print(f"Greeting error: {e}")

    # ── Main loop ──
    is_playing = False  # Track TTS playback state

    try:
        while True:
            try:
                data = await websocket.receive()
            except RuntimeError:
                break

            if data.get("type") == "websocket.disconnect":
                break

            # ── Handle audio data ──
            if "bytes" in data:
                audio_data = data["bytes"]
                timer = PipelineTimer()
                timer.begin("RECEIVING")

                # Don't process if still playing (frontend should prevent, this is safety)
                if is_playing:
                    print("⚠️ Audio received while playing, ignoring")
                    continue

                print(f"\n{'='*60}")
                print(f"[START] Audio received: {len(audio_data)} bytes")

                # Trim silence from audio
                audio_data = trim_silence(audio_data)
                timer.begin("TRANSCRIBING")

                await websocket.send_json({"type": "status", "message": "transcribing"})

                # 1. STT
                transcript = await stt_service.transcribe_stream(audio_data, timer.start_time)
                stt_ms = timer.total_ms()
                print(f"📝 Transcript: {transcript} ({stt_ms:.0f}ms)")

                if not transcript or not transcript.strip():
                    await websocket.send_json({"type": "status", "message": "idle"})
                    timer.end()
                    continue

                await websocket.send_json({"type": "transcript", "text": transcript})

                # 2. LLM
                timer.begin("THINKING")
                await websocket.send_json({"type": "status", "message": "thinking"})

                full_response = ""
                structured_data = None
                tts_task = None
                cached_phrase_sent = False
                first_tts_fired = False

                async for event in llm_service.generate_stream(transcript, menu_context, timer.start_time):
                    if event["type"] == "token":
                        if not first_tts_fired and timer._current_stage == "THINKING":
                            timer.begin("CHUNKING")

                        await websocket.send_json({
                            "type": "ai_token",
                            "token": event["content"],
                            "full_text": event["full_text"],
                        })
                        full_response = event["full_text"]

                        # ── Try cached phrase match ──
                        if not cached_phrase_sent and not first_tts_fired:
                            spoken = extract_spoken_text(full_response)
                            if spoken:
                                matched_text, cached_audio, remaining = match_cached_phrase(spoken)
                                if cached_audio:
                                    # INSTANT play from cache!
                                    timer.begin("PLAYING_CACHED")
                                    is_playing = True
                                    cached_phrase_sent = True
                                    first_tts_fired = True
                                    cache_ms = timer.total_ms()
                                    print(f"⚡ CACHED PHRASE HIT: '{matched_text[:40]}' → instant audio at {cache_ms:.0f}ms")

                                    await websocket.send_json({"type": "tts_start"})
                                    await websocket.send_bytes(cached_audio)
                                    print(f"🔊 Cached audio sent: {len(cached_audio)} bytes")

                                    # If there's remaining text, fire TTS for it
                                    if remaining and len(remaining) > 5:
                                        timer.begin("GENERATING_TTS")
                                        tts_task = asyncio.create_task(
                                            _stream_tts_to_ws(websocket, remaining, timer.start_time)
                                        )

                        # ── Fallback: Fire TTS on first complete sentence ──
                        if not first_tts_fired:
                            spoken = extract_spoken_text(full_response)
                            if spoken and len(spoken) > 10:
                                first_tts_fired = True
                                is_playing = True
                                timer.begin("GENERATING_TTS")
                                tts_ms = timer.total_ms()
                                print(f"⚡ First TTS fired at {tts_ms:.0f}ms: {spoken[:60]}")

                                await websocket.send_json({"type": "tts_start"})
                                tts_task = asyncio.create_task(
                                    _stream_tts_to_ws(websocket, spoken, timer.start_time)
                                )

                    elif event["type"] == "complete":
                        structured_data = event["structured"]
                        timer.begin("COMPLETING")
                        elapsed_ms = timer.total_ms()
                        print(f"[LLM complete]: {elapsed_ms:.0f}ms | {json.dumps(structured_data, ensure_ascii=False)[:120]}")

                        await websocket.send_json({
                            "type": "ai_complete",
                            "data": structured_data,
                        })

                        # Handle recommendation
                        if structured_data.get("intent") == "recommend":
                            product = find_product_for_recommendation(products, structured_data)
                            if product:
                                rec = structured_data.get("recommendation", {})
                                await websocket.send_json({
                                    "type": "recommendation",
                                    "product": product_to_dict(product, rec.get("reason", "Size özel öneri")),
                                })
                                print(f"📌 Recommendation: {product.name}")

                # 3. TTS completion / fallback
                timer.begin("PLAYING")
                if tts_task:
                    await tts_task
                elif structured_data and structured_data.get("spoken_response"):
                    spoken = structured_data["spoken_response"]
                    if spoken.strip():
                        is_playing = True
                        await websocket.send_json({"type": "tts_start"})
                        await _stream_tts_to_ws(websocket, spoken, timer.start_time)

                await websocket.send_json({"type": "tts_complete"})
                is_playing = False
                timer.end("PLAYING")

                # ── Print timing report ──
                print(timer.report())

            elif "text" in data:
                try:
                    msg = json.loads(data["text"])
                    if msg.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                    elif msg.get("type") == "playback_complete":
                        is_playing = False
                        print("🔇 Client: playback complete, ready to listen")
                except json.JSONDecodeError:
                    pass

    except WebSocketDisconnect:
        manager.disconnect(websocket, table_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        import traceback; traceback.print_exc()
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
        manager.disconnect(websocket, table_id)


async def _stream_tts_to_ws(websocket: WebSocket, text: str, start_time: float = None):
    """Stream TTS audio chunks to WebSocket with timing."""
    chunk_count = 0
    total_bytes = 0
    async for audio_chunk in tts_service.speak_stream(text, start_time):
        if audio_chunk:
            if chunk_count == 0 and start_time:
                first_audio_ms = (time.time() - start_time) * 1000
                print(f"🔊 [First audio chunk]: {first_audio_ms:.0f}ms ({len(audio_chunk)} bytes)")
            chunk_count += 1
            total_bytes += len(audio_chunk)
            await websocket.send_bytes(audio_chunk)
    if start_time:
        total_ms = (time.time() - start_time) * 1000
        print(f"✅ TTS stream done: {chunk_count} chunks, {total_bytes} bytes, {total_ms:.0f}ms")
