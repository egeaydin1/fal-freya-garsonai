from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import ai_routes, voice_routes, auth_routes, restaurant_routes, menu_routes
from core.database import engine, Base

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="GarsonAI API", version="1.0.0")

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
app.include_router(ai_routes.router)  # Legacy, keep for compatibility

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
