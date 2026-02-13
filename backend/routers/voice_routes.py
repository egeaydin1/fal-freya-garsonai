from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session, joinedload
from core.database import get_db
from models.models import Table, Product
from services import STTService, TTSService, LLMService
from websocket.manager import manager
import json
import asyncio
import time
import re

router = APIRouter()

stt_service = STTService()
tts_service = TTSService()
llm_service = LLMService()


def build_menu_context(products):
    """Build rich menu context with IDs, categories, descriptions, allergens for LLM."""
    categories = {}
    for p in products:
        cat = getattr(p, 'category', None) or 'Diğer'
        if cat not in categories:
            categories[cat] = []
        allergen_names = []
        try:
            allergen_names = [a.name for a in p.allergens]
        except Exception:
            pass
        allergen_str = f" [Alerjen: {', '.join(allergen_names)}]" if allergen_names else ""
        categories[cat].append(
            f"  - ID:{p.id} | {p.name} | {p.price}₺ | {p.description or 'açıklama yok'}{allergen_str}"
        )

    lines = []
    for cat, items in categories.items():
        lines.append(f"\n📂 {cat}:")
        lines.extend(items)
    return "\n".join(lines)


def find_product_for_recommendation(products, structured_data):
    """Find the product object for a recommendation from structured LLM data."""
    rec = structured_data.get("recommendation", {})
    if not rec:
        return None

    # Try by product_id first
    pid = rec.get("product_id")
    if pid:
        for p in products:
            if p.id == pid:
                return p

    # Fallback: by name
    pname = rec.get("product_name", "")
    if pname:
        for p in products:
            if pname.lower() in p.name.lower():
                return p

    return None


def product_to_dict(p, reason=""):
    """Serialize a Product ORM object to a dict for WebSocket."""
    allergens = []
    try:
        allergens = [{"id": a.id, "name": a.name, "icon": a.icon} for a in p.allergens]
    except Exception:
        pass
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "price": p.price,
        "image_url": p.image_url,
        "category": getattr(p, "category", None),
        "allergens": allergens,
        "reason": reason,
    }


def extract_spoken_text(full_response: str) -> str | None:
    """Try to extract spoken_response from partial JSON in LLM stream."""
    try:
        m = re.search(r'"spoken_response"\s*:\s*"([^"]*)"', full_response)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


@router.websocket("/ws/voice/{table_id}")
async def voice_websocket(
    websocket: WebSocket, table_id: str, db: Session = Depends(get_db)
):
    """Optimized voice pipeline: Audio → STT → LLM stream → parallel TTS → Audio."""
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

    # Send welcome greeting text on connect (no TTS - browser autoplay blocks it)
    try:
        greeting = "Merhaba, restoranımıza hoş geldiniz! Size nasıl yardımcı olabilirim? 🎤 Mikrofona basarak sipariş verebilir veya öneri isteyebilirsiniz."
        await websocket.send_json({
            "type": "greeting",
            "text": greeting,
        })
    except Exception as e:
        print(f"Greeting error: {e}")

    try:
        while True:
            try:
                data = await websocket.receive()
            except RuntimeError:
                break

            if data.get("type") == "websocket.disconnect":
                break

            if "bytes" in data:
                audio_data = data["bytes"]
                start_time = time.time()
                print(f"\n{'='*60}")
                print(f"[START] Audio received: {len(audio_data)} bytes")

                await websocket.send_json({"type": "status", "message": "processing"})

                # 1. STT (OPT-1: base64 encode, no CDN upload)
                transcript = await stt_service.transcribe_stream(audio_data, start_time)
                print(f"📝 Transcript: {transcript}")

                if not transcript or not transcript.strip():
                    await websocket.send_json({"type": "status", "message": "idle"})
                    continue

                await websocket.send_json({"type": "transcript", "text": transcript})

                # 2. LLM Stream (OPT-2: OpenAI streaming for low TTFT)
                full_response = ""
                structured_data = None
                tts_task = None
                first_sentence_fired = False

                async for event in llm_service.generate_stream(transcript, menu_context, start_time):
                    if event["type"] == "token":
                        await websocket.send_json({
                            "type": "ai_token",
                            "token": event["content"],
                            "full_text": event["full_text"],
                        })
                        full_response = event["full_text"]

                        # OPT-3: Fire TTS on first complete sentence in parallel
                        if not first_sentence_fired:
                            spoken = extract_spoken_text(full_response)
                            if spoken and len(spoken) > 10:
                                first_sentence_fired = True
                                print(f"⚡ Parallel TTS: {spoken[:60]}...")
                                await websocket.send_json({"type": "tts_start"})
                                tts_task = asyncio.create_task(
                                    _stream_tts_to_ws(websocket, spoken, start_time)
                                )

                    elif event["type"] == "complete":
                        structured_data = event["structured"]
                        elapsed = time.time() - start_time
                        print(f"[LLM complete]: {elapsed:.3f}s | {structured_data}")

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
                                    "product": product_to_dict(
                                        product,
                                        rec.get("reason", "Size özel öneri"),
                                    ),
                                })
                                print(f"📌 Recommendation: {product.name}")

                # 3. TTS completion
                if tts_task:
                    await tts_task
                    await websocket.send_json({"type": "tts_complete"})
                elif structured_data and structured_data.get("spoken_response"):
                    spoken = structured_data["spoken_response"]
                    if spoken.strip():
                        await websocket.send_json({"type": "tts_start"})
                        await _stream_tts_to_ws(websocket, spoken, start_time)
                        await websocket.send_json({"type": "tts_complete"})

                elapsed = time.time() - start_time
                print(f"[COMPLETE] Pipeline: {elapsed:.3f}s")
                print(f"{'='*60}\n")

            elif "text" in data:
                msg = json.loads(data["text"])
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

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
    """Stream TTS audio chunks to WebSocket."""
    chunk_count = 0
    async for audio_chunk in tts_service.speak_stream(text, start_time):
        if audio_chunk:
            if chunk_count == 0 and start_time:
                print(f"[Audio start]: {time.time() - start_time:.3f}s")
            chunk_count += 1
            await websocket.send_bytes(audio_chunk)


async def _send_tts(websocket: WebSocket, text: str):
    """Send greeting TTS (fire-and-forget)."""
    try:
        await websocket.send_json({"type": "tts_start"})
        await _stream_tts_to_ws(websocket, text)
        await websocket.send_json({"type": "tts_complete"})
    except Exception as e:
        print(f"Greeting TTS error: {e}")
