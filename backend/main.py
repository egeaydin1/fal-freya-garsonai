from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from routers import  voice_routes, auth_routes, restaurant_routes, menu_routes
from core.database import engine, Base, get_db
from core.auth import get_current_restaurant
from models.models import Restaurant
from services.tts_warmer import start_tts_warmer, stop_tts_warmer
from services.tts_cache import get_tts_cache
from services.stt_warmer import start_stt_warmer, stop_stt_warmer
from websocket.manager import manager
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
import asyncio

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
    
    # Pre-cache TTS for known starter sentences
    print("🔥 Warming TTS sentence cache...")
    tts_cache = get_tts_cache()
    asyncio.create_task(tts_cache.warm_cache())
    
    # STT warmer — keeps container hot, prevents cold-start latency
    print("🚀 Starting STT warmer...")
    start_stt_warmer(interval=45)
    
    yield
    
    # Shutdown: Stop warmers
    print("🛑 Stopping warmers...")
    stop_tts_warmer()
    stop_stt_warmer()


app = FastAPI(
    title="GarsonAI API", 
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:80",
        "http://127.0.0.1",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:80",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_routes.router)
app.include_router(restaurant_routes.router)
app.include_router(menu_routes.router)
app.include_router(voice_routes.router)
# app.include_router(ai_routes.router)  # Legacy, keep for compatibility

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