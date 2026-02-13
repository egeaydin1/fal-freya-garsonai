from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session, joinedload
from core.database import get_db
from models.models import Table, Product
from services.partial_stt import PartialSTTService
from services.streaming_llm_bridge import get_llm_bridge
from websocket.manager import manager
from websocket.voice_session import SessionManager
import json
import asyncio
import time

router = APIRouter()

# Initialize services
partial_stt = PartialSTTService()
llm_bridge = get_llm_bridge()
session_manager = SessionManager()

@router.websocket("/ws/voice/{table_id}")
async def voice_websocket(websocket: WebSocket, table_id: str, db: Session = Depends(get_db)):
    """
    Full-duplex streaming voice AI endpoint
    Architecture:
      - Incremental STT: Process audio chunks while user speaks
      - Early LLM trigger: Start LLM at sentence boundaries (punctuation or 400ms silence)
      - Parallel TTS: Begin audio playback on first complete LLM sentence
      - Barge-in: User can interrupt AI mid-speech
    """
    await manager.connect(websocket, table_id)
    
    # Verify table exists
    table = db.query(Table).filter(Table.qr_token == table_id).first()
    if not table:
        print(f"❌ Table not found with qr_token: {table_id}")
        await websocket.close(code=4004, reason="Table not found")
        return
    
    print(f"✅ Table found: {table.table_number} (Restaurant ID: {table.restaurant_id})")
    
    # Get menu context for LLM (with allergens and product IDs)
    products = db.query(Product).options(joinedload(Product.allergens)).filter(
        Product.restaurant_id == table.restaurant_id,
        Product.is_available == True
    ).all()
    
    def _build_product_line(p):
        line = f"- [ID:{p.id}] {p.name}: {p.price}TL"
        if p.description:
            line += f" ({p.description})"
        if p.category:
            line += f" [Kategori: {p.category}]"
        if p.allergens:
            allergen_names = ", ".join(a.name for a in p.allergens)
            line += f" [Alerjen: {allergen_names}]"
        return line
    
    menu_context = "\n".join([_build_product_line(p) for p in products])
    
    # Create voice session for this connection
    session = session_manager.create_session(table_id, menu_context)
    print(f"🔗 Session created: {session.session_id}")
    
    # Track partial STT processing task
    partial_stt_task: asyncio.Task = None
    
    async def _handle_partial_stt_result(partial_result: dict, ws: WebSocket, sess):
        """Handle partial STT result from background task."""
        nonlocal partial_stt_task
        
        if partial_result.get("skipped") or partial_result.get("error"):
            if partial_result.get("error"):
                print(f"⚠️ Partial STT failed: {partial_result.get('error')}")
            sess.state = "LISTENING"
            return
        
        if partial_result and partial_result.get("text"):
            transcript_text = partial_result["text"]
            confidence = partial_result.get("confidence", 0.0)
            
            # Merge with existing transcript
            sess.partial_transcript = partial_stt.merge_transcripts(
                sess.partial_transcript,
                transcript_text
            )
            
            print(f"📝 Partial: '{sess.partial_transcript}' (conf: {confidence:.2f})")
            
            # Send partial transcript to client
            try:
                await ws.send_json({
                    "type": "partial_transcript",
                    "text": sess.partial_transcript,
                    "confidence": confidence,
                    "is_final": False
                })
            except Exception:
                pass  # WebSocket may have closed
            
            sess.state = "LISTENING"
    
    async def _run_partial_stt(audio_data: bytes, ws: WebSocket, sess):
        """Run partial STT in background without blocking WebSocket loop."""
        try:
            partial_result = await partial_stt.transcribe_partial(
                audio_data,
                sess.start_time,
                is_final=False
            )
            await _handle_partial_stt_result(partial_result, ws, sess)
        except Exception as e:
            print(f"⚠️ Background partial STT error: {e}")
            sess.state = "LISTENING"
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive()
            
            if "bytes" in data:
                # Audio chunk received (500ms) - full-duplex incremental processing
                chunk = data["bytes"]
                session.add_audio_chunk(chunk)
                
                # Check if we should process partial STT (every 1.2s worth of audio)
                # Run as background task so WebSocket loop keeps receiving chunks
                if session.can_process_partial_stt():
                    # Don't start new STT if previous is still running
                    if partial_stt_task and not partial_stt_task.done():
                        continue
                    
                    print(f"⚡ Triggering partial STT (buffer: {len(session.audio_buffer)} bytes, chunks: {session.chunk_count})")
                    session.state = "PROCESSING_STT"
                    session.last_partial_stt_time = time.time()
                    session.chunk_count = 0
                    
                    # Snapshot audio buffer and launch background task
                    audio_data = bytes(session.audio_buffer)
                    partial_stt_task = asyncio.create_task(
                        _run_partial_stt(audio_data, websocket, session)
                    )
                
                continue
                
            elif "text" in data:
                message = json.loads(data["text"])
                
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue
                
                elif message.get("type") == "interrupt":
                    # Barge-in: User interrupted AI mid-speech
                    print(f"🛑 BARGE-IN: User interrupted AI (session: {session.session_id})")
                    
                    # Cancel background partial STT
                    if partial_stt_task and not partial_stt_task.done():
                        partial_stt_task.cancel()
                        partial_stt_task = None
                    
                    # Cancel active LLM/TTS streams
                    await llm_bridge.cancel_active_streams(session.session_id)
                    await session.cancel_active_streams()
                    
                    # Reset session state
                    session.state = "LISTENING"
                    session.partial_transcript = ""
                    session.audio_buffer.clear()
                    
                    await websocket.send_json({
                        "type": "interrupt_ack",
                        "message": "AI interrupted"
                    })
                    continue
                
                elif message.get("type") == "audio_end":
                    # Cancel any running partial STT - we'll do final STT instead
                    if partial_stt_task and not partial_stt_task.done():
                        partial_stt_task.cancel()
                        partial_stt_task = None
                    
                    # User stopped speaking - process final STT
                    print(f"🎤 Audio end (buffer: {len(session.audio_buffer)} bytes, partial: '{session.partial_transcript}')")
                    
                    if not session.audio_buffer and not session.partial_transcript:
                        print("⚠️ No audio or transcript")
                        session.state = "IDLE"
                        continue
                    
                    # If we have buffered audio, do final STT
                    if session.audio_buffer:
                        session.state = "PROCESSING_STT"
                        await websocket.send_json({"type": "status", "message": "processing"})
                        
                        # Final STT with accumulated audio
                        audio_data = bytes(session.audio_buffer)
                        
                        try:
                            final_result = await partial_stt.transcribe_partial(
                                audio_data,
                                session.start_time,
                                is_final=True
                            )
                        except Exception as e:
                            print(f"❌ STT failed with exception: {e}")
                            final_result = {"error": str(e)}
                        
                        # Check if transcription was skipped or failed
                        if final_result.get("skipped"):
                            print(f"⏭️ Skipped transcription (audio too small)")
                            session.audio_buffer.clear()
                            session.state = "IDLE"
                            continue
                        
                        if final_result.get("error"):
                            print(f"⚠️ STT failed: {final_result.get('error')}")
                            session.audio_buffer.clear()
                            session.state = "IDLE"
                            await websocket.send_json({
                                "type": "error",
                                "message": "Ses tanıma servisi geçici olarak kullanılamıyor. Lütfen tekrar deneyin."
                            })
                            continue
                        
                        if final_result and final_result.get("text"):
                            final_text = final_result["text"]
                            
                            # Merge with partial transcript
                            full_transcript = partial_stt.merge_transcripts(
                                session.partial_transcript,
                                final_text
                            )
                            
                            session.partial_transcript = full_transcript
                            print(f"📝 Final transcript: '{full_transcript}'")
                            
                            await websocket.send_json({
                                "type": "transcript",
                                "text": full_transcript,
                                "is_final": True
                            })
                    
                    # If we already have a transcript (from partial STT), use it
                    transcript = session.partial_transcript.strip()
                    
                    if not transcript:
                        print("⏭️ No speech detected, returning to IDLE")
                        session.state = "IDLE"
                        continue
                    
                    # Start LLM+TTS pipeline
                    session.state = "GENERATING_LLM"
                    await websocket.send_json({
                        "type": "status",
                        "message": "thinking"
                    })
                    
                    try:
                        structured_data = await llm_bridge.process_stream(
                            transcript=transcript,
                            menu_context=menu_context,
                            start_time=session.start_time,
                            websocket_send_json=websocket.send_json,
                            websocket_send_bytes=websocket.send_bytes,
                            session_id=session.session_id,
                            products=products
                        )
                        
                        # Transition to TTS streaming
                        session.state = "STREAMING_TTS"
                        
                        # Reset for next turn
                        session.partial_transcript = ""
                        session.audio_buffer.clear()
                        session.state = "IDLE"
                        
                    except Exception as e:
                        print(f"❌ LLM/TTS error: {e}")
                        await websocket.send_json({
                            "type": "error",
                            "message": str(e)
                        })
                        session.state = "IDLE"
            else:
                print(f"⚠️ Unhandled data type - data keys: {data.keys() if isinstance(data, dict) else 'not a dict'}")
                    
    except WebSocketDisconnect:
        print(f"🔌 WebSocket disconnected: {session.session_id}")
        if partial_stt_task and not partial_stt_task.done():
            partial_stt_task.cancel()
        llm_bridge.clear_session_history(session.session_id)
        await session_manager.remove_session(session.session_id)
        manager.disconnect(websocket, table_id)
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        import traceback
        traceback.print_exc()
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
        await session_manager.remove_session(session.session_id)
        manager.disconnect(websocket, table_id)
