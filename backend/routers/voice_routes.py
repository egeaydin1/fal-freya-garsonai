from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from core.database import get_db
from models.models import Table, Product
from services import STTService, TTSService, LLMService
from websocket.manager import manager
import json
import asyncio
import time

router = APIRouter()

# Initialize services
stt_service = STTService()
tts_service = TTSService()
llm_service = LLMService()

@router.websocket("/ws/voice/{table_id}")
async def voice_websocket(websocket: WebSocket, table_id: str, db: Session = Depends(get_db)):
    """
    Streaming voice AI endpoint
    Flow: Audio chunks -> STT -> LLM stream -> TTS stream -> Audio chunks back
    """
    await manager.connect(websocket, table_id)
    
    # Verify table exists
    table = db.query(Table).filter(Table.qr_token == table_id).first()
    if not table:
        await websocket.close(code=4004, reason="Table not found")
        return
    
    # Get menu context for LLM
    products = db.query(Product).filter(
        Product.restaurant_id == table.restaurant_id,
        Product.is_available == True
    ).all()
    
    menu_context = "\n".join([
        f"- {p.name}: {p.price}TL ({p.description})"
        for p in products
    ])
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive()
            
            if "bytes" in data:
                # Audio chunk received - process immediately
                audio_data = data["bytes"]
                start_time = time.time()
                print(f"\n{'='*60}")
                print(f"[START] User audio received: 00:00.000")
                print(f"🎤 Audio chunk size: {len(audio_data)} bytes")
                
                await websocket.send_json({"type": "status", "message": "processing"})
                
                # 1. STT - Transcribe audio
                transcript = await stt_service.transcribe_stream(audio_data, start_time)
                print(f"📝 Transcript: {transcript}")
                
                if transcript and transcript.strip():
                    await websocket.send_json({
                        "type": "transcript",
                        "text": transcript
                    })
                    
                    # 2. LLM - Stream response with parallel TTS trigger
                    full_response = ""
                    structured_data = None
                    first_token_logged = False
                    first_sentence_complete = False
                    tts_task = None
                    first_sentence = ""
                    
                    async for llm_event in llm_service.generate_stream(transcript, menu_context, start_time):
                        if llm_event["type"] == "token":
                            if not first_token_logged:
                                elapsed = time.time() - start_time
                                print(f"[LLM first token]: {elapsed:06.3f}s")
                                first_token_logged = True
                                
                            await websocket.send_json({
                                "type": "ai_token",
                                "token": llm_event["content"],
                                "full_text": llm_event["full_text"]
                            })
                            full_response = llm_event["full_text"]
                            
                            # Check if first sentence is complete (ends with . ! ?)
                            # and start TTS in parallel
                            if not first_sentence_complete and full_response:
                                import re
                                # Look for sentence-ending punctuation
                                match = re.search(r'[.!?]\s*', full_response)
                                if match:
                                    first_sentence = full_response[:match.end()].strip()
                                    
                                    # Extract just the spoken part (remove JSON if present)
                                    if '"spoken_response"' in first_sentence:
                                        try:
                                            # Extract from JSON
                                            spoken_match = re.search(r'"spoken_response"\s*:\s*"([^"]+)"', full_response)
                                            if spoken_match:
                                                first_sentence = spoken_match.group(1)
                                                
                                                # Start TTS in background
                                                print(f"⚡ Parallel TTS: Starting TTS for first sentence: {first_sentence[:50]}...")
                                                first_sentence_complete = True
                                                
                                                # Send tts_start immediately
                                                await websocket.send_json({"type": "tts_start"})
                                                
                                                # Start TTS task in parallel
                                                async def stream_tts_parallel():
                                                    chunk_count = 0
                                                    async for audio_chunk in tts_service.speak_stream(first_sentence, start_time):
                                                        if audio_chunk:
                                                            if chunk_count == 0:
                                                                elapsed = time.time() - start_time
                                                                print(f"[Audio playback start]: {elapsed:06.3f}s (parallel TTS first chunk)")
                                                            chunk_count += 1
                                                            await websocket.send_bytes(audio_chunk)
                                                
                                                tts_task = asyncio.create_task(stream_tts_parallel())
                                        except Exception as e:
                                            print(f"⚠️ Parallel TTS parse error: {e}")
                            
                        elif llm_event["type"] == "complete":
                            structured_data = llm_event["structured"]
                            elapsed = time.time() - start_time
                            print(f"[LLM complete]: {elapsed:06.3f}s")
                            print(f"🎯 LLM Complete - Structured data: {structured_data}")
                            await websocket.send_json({
                                "type": "ai_complete",
                                "data": structured_data
                            })
                    
                    # 3. Wait for parallel TTS or start new TTS
                    if tts_task:
                        # Wait for parallel TTS to complete
                        print("⏳ Waiting for parallel TTS to complete...")
                        await tts_task
                        await websocket.send_json({"type": "tts_complete"})
                        elapsed = time.time() - start_time
                        print(f"[COMPLETE] Total pipeline (with parallel TTS): {elapsed:06.3f}s")
                        print(f"{'='*60}\n")
                    else:
                        # Fallback: No parallel TTS was triggered, do full TTS
                        print(f"🔍 Fallback TTS: Starting full TTS for complete response")
                        
                        if structured_data and "spoken_response" in structured_data:
                            tts_text = structured_data["spoken_response"]
                        else:
                            tts_text = full_response
                        
                        await websocket.send_json({"type": "tts_start"})
                        
                        chunk_count = 0
                        async for audio_chunk in tts_service.speak_stream(tts_text, start_time):
                            if audio_chunk:
                                if chunk_count == 0:
                                    elapsed = time.time() - start_time
                                    print(f"[Audio playback start]: {elapsed:06.3f}s (fallback TTS first chunk)")
                                chunk_count += 1
                                await websocket.send_bytes(audio_chunk)
                        
                        await websocket.send_json({"type": "tts_complete"})
                        elapsed = time.time() - start_time
                        print(f"[COMPLETE] Total pipeline (with fallback TTS): {elapsed:06.3f}s")
                        print(f"{'='*60}\n")
                        if structured_data and "spoken_response" in structured_data:
                            spoken_text = structured_data["spoken_response"]
                            print(f"🗣️ TTS: Will synthesize: {spoken_text}")
                            
                            if spoken_text and spoken_text.strip():
                                await websocket.send_json({"type": "tts_start"})
                                
                                chunk_count = 0
                                async for audio_chunk in tts_service.speak_stream(spoken_text, start_time):
                                    if audio_chunk:
                                        if chunk_count == 0:
                                            elapsed = time.time() - start_time
                                            print(f"[Audio playback start]: {elapsed:06.3f}s (first chunk sent)")
                                        chunk_count += 1
                                        await websocket.send_bytes(audio_chunk)
                                
                                await websocket.send_json({"type": "tts_complete"})
                                elapsed = time.time() - start_time
                                print(f"[COMPLETE] Total pipeline: {elapsed:06.3f}s")
                                print(f"{'='*60}\n")
                            else:
                                print("⚠️ No spoken_response to synthesize")
                        else:
                            print(f"❌ TTS: No structured_data or spoken_response. Data: {structured_data}")
                
            elif "text" in data:
                message = json.loads(data["text"])
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    
    except WebSocketDisconnect:
        manager.disconnect(websocket, table_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
        manager.disconnect(websocket, table_id)
