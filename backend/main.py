from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from routers import  voice_routes, auth_routes, restaurant_routes, menu_routes
from routers import voice_routes_v2
from core.database import engine, Base, get_db
from core.config import get_settings
from core.auth import get_current_restaurant
from models.models import Restaurant
from services.tts_warmer import start_tts_warmer, stop_tts_warmer
from services.phrase_cache import load_or_generate_all as load_phrase_cache
from websocket.manager import manager
from sqlalchemy.orm import Session
# Note: STT warmer disabled - real requests keep container warm
# from services.stt_warmer import start_stt_warmer, stop_stt_warmer
from contextlib import asynccontextmanager
import os

# Create uploads directory
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Create database tables
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for startup/shutdown tasks
    """
    # Startup: Start warmers
    print("🚀 Starting TTS warmer...")
    start_tts_warmer(interval=30)  # Keep warm every 30s
    
    # Load phrase cache for v2 pipeline
    settings = get_settings()
    if settings.VOICE_PIPELINE == "v2":
        print("🔊 Loading pre-cached phrases for v2 pipeline...")
        load_phrase_cache()
    print(f"🎙️ Voice pipeline: {settings.VOICE_PIPELINE}")
    
    yield
    
    # Shutdown: Stop warmers
    print("🛑 Stopping warmers...")
    stop_tts_warmer()
    # stop_stt_warmer()


app = FastAPI(
    title="GarsonAI API", 
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_routes.router)
app.include_router(restaurant_routes.router)
app.include_router(menu_routes.router)

# Voice pipeline selection via VOICE_PIPELINE env var
_voice_settings = get_settings()
if _voice_settings.VOICE_PIPELINE == "v2":
    print("🚀 Using optimized voice pipeline v2")
    app.include_router(voice_routes_v2.router)
else:
    print("🔄 Using original voice pipeline v1")
    app.include_router(voice_routes.router)
# app.include_router(ai_routes.router)  # Legacy, keep for compatibility

# Mount static files for uploaded images
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

@app.get("/")
def root():
    return {
        "app": "GarsonAI",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}
@app.websocket("/ws/restaurant/{restaurant_id}")
async def websocket_restaurant_endpoint(
    websocket: WebSocket,
    restaurant_id: int,
    db: Session = Depends(get_db)
):
    """WebSocket endpoint for restaurant dashboard real-time updates"""
    await manager.connect_restaurant(websocket, restaurant_id)
    try:
        while True:
            # Keep connection alive and listen for messages
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_restaurant(websocket, restaurant_id)