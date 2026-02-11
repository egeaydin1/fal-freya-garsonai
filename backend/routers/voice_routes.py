from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from core.database import get_db
from models.models import Table, Product
from services import STTService, TTSService, LLMService
from websocket.manager import manager
import json
import asyncio

router = APIRouter()

# Initialize services (keep warm)
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
                # Audio chunk received
                audio_data = data["bytes"]
                
                # Send status
                await websocket.send_json({"type": "status", "message": "processing"})
                
                # 1. STT - Transcribe
                transcript = await stt_service.transcribe_stream(audio_data)
                
                if transcript:
                    await websocket.send_json({
                        "type": "transcript",
                        "text": transcript
                    })
                    
                    # 2. LLM - Stream response
                    full_response = ""
                    structured_data = None
                    
                    async for llm_event in llm_service.generate_stream(transcript, menu_context):
                        if llm_event["type"] == "token":
                            # Send progressive text
                            await websocket.send_json({
                                "type": "ai_token",
                                "token": llm_event["content"],
                                "full_text": llm_event["full_text"]
                            })
                            full_response = llm_event["full_text"]
                            
                        elif llm_event["type"] == "complete":
                            structured_data = llm_event["structured"]
                            await websocket.send_json({
                                "type": "ai_complete",
                                "data": structured_data
                            })
                    
                    # 3. TTS - Stream audio
                    if structured_data and "spoken_response" in structured_data:
                        spoken_text = structured_data["spoken_response"]
                        
                        await websocket.send_json({
                            "type": "tts_start"
                        })
                        
                        # Stream audio chunks
                        async for audio_chunk in tts_service.speak_stream(spoken_text):
                            if audio_chunk:
                                await websocket.send_bytes(audio_chunk)
                        
                        await websocket.send_json({
                            "type": "tts_complete"
                        })
                
            elif "text" in data:
                # Text message (for control)
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
