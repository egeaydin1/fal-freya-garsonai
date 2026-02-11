from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import  voice_routes, auth_routes, restaurant_routes, menu_routes
from core.database import engine, Base
from services.tts_warmer import start_tts_warmer, stop_tts_warmer
# Note: STT warmer disabled - real requests keep container warm
# from services.stt_warmer import start_stt_warmer, stop_stt_warmer
from contextlib import asynccontextmanager

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
    
    # STT warmer disabled - real user requests keep it warm enough
    # print("🚀 Starting STT warmer...")
    # start_stt_warmer(interval=30)
    
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
