from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import ai_routes

app = FastAPI()

app.include_router(ai_routes.router)

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_methods=["*"],
	allow_headers=["*"],
)