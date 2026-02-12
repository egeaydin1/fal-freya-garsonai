from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from core.database import get_db
from models.models import Table, Product
from services import STTService
from services.partial_stt import PartialSTTService
from services.streaming_llm_bridge import get_llm_bridge
from websocket.manager import manager
from websocket.voice_session import SessionManager
import json
import asyncio
import time

router = APIRouter()

# Initialize services
stt_service = STTService()
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
    
    # Get menu context for LLM
    products = db.query(Product).filter(
        Product.restaurant_id == table.restaurant_id,
        Product.is_available == True
    ).all()
    
    menu_context = "\n".join([
        f"- {p.name}: {p.price}TL ({p.description})"
        for p in products
    ])
    
    # Create voice session for this connection
    session = session_manager.create_session(table_id, menu_context)
    print(f"🔗 Session created: {session.session_id}")
    
    # Track partial STT processing task
    partial_stt_task = None
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive()
            print(f"🔍 DEBUG: Received data - type: {type(data)}, keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
            
            if "bytes" in data:
                # Audio chunk received (500ms) - full-duplex incremental processing
                chunk = data["bytes"]
                session.add_audio_chunk(chunk)
                
                print(f"📦 Audio chunk: {len(chunk)} bytes | Buffer: {len(session.audio_buffer)} bytes | State: {session.state}")
                
                # Instant UI feedback
                await websocket.send_json({"type": "status", "message": "receiving"})
                
                # Check if we should process partial STT (every 1.2s worth of audio)
                if session.can_process_partial_stt():
                    print(f"⚡ Triggering partial STT (buffer: {len(session.audio_buffer)} bytes)")
                    session.state = "PROCESSING_STT"
                    
                    # Process partial STT in background
                    audio_data = bytes(session.audio_buffer)
                    partial_result = await partial_stt.transcribe_partial(
                        audio_data,
                        session.start_time,
                        is_final=False
                    )
                    
                    # Skip if transcription was skipped or failed
                    if partial_result.get("skipped"):
                        session.state = "LISTENING"
                        session.last_partial_stt_time = time.time()
                        continue
                    
                    if partial_result.get("error"):
                        print(f"⚠️ Partial STT failed: {partial_result.get('error')}")
                        session.state = "LISTENING"
                        session.last_partial_stt_time = time.time()
                        continue
                    
                    if partial_result and partial_result.get("text"):
                        transcript_text = partial_result["text"]
                        confidence = partial_result.get("confidence", 0.0)
                        
                        # Merge with existing transcript
                        session.partial_transcript = partial_stt.merge_transcripts(
                            session.partial_transcript,
                            transcript_text
                        )
                        
                        print(f"📝 Partial: '{session.partial_transcript}' (conf: {confidence:.2f})")
                        
                        # Send partial transcript to client
                        await websocket.send_json({
                            "type": "partial_transcript",
                            "text": session.partial_transcript,
                            "confidence": confidence,
                            "is_final": False
                        })
                        
                        session.last_partial_stt_time = time.time()
                        session.state = "LISTENING"
                        
                        # Check if we should trigger LLM early (sentence boundary + silence)
                        if session.should_trigger_llm():
                            print(f"⚡⚡ Early LLM trigger! Transcript: '{session.partial_transcript[:100]}...'")
                            
                            # Transition to LLM generation
                            session.state = "GENERATING_LLM"
                            await websocket.send_json({
                                "type": "status",
                                "message": "thinking"
                            })
                            
                            # Start LLM+TTS pipeline
                            try:
                                structured_data = await llm_bridge.process_stream(
                                    transcript=session.partial_transcript,
                                    menu_context=menu_context,
                                    start_time=session.start_time,
                                    websocket_send_json=websocket.send_json,
                                    websocket_send_bytes=websocket.send_bytes,
                                    session_id=session.session_id
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
                
                continue
                
            elif "text" in data:
                message = json.loads(data["text"])
                
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue
                
                elif message.get("type") == "interrupt":
                    # Barge-in: User interrupted AI mid-speech
                    print(f"🛑 BARGE-IN: User interrupted AI (session: {session.session_id})")
                    
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
                            session_id=session.session_id
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
