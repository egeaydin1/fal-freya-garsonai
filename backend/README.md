# GarsonAI Backend

Real-time voice AI waiter system with streaming STT, LLM, and TTS.

## Features

- 🎤 Streaming STT (Freya STT)
- 🧠 Streaming LLM (Gemini 2.5 Flash via OpenRouter)
- 🔊 Streaming TTS (Freya TTS)
- 🔐 JWT Authentication
- 🍽 Restaurant Management
- 📱 QR-based Table System
- 🛒 Real-time Orders
- ⚡ WebSocket Voice Pipeline

## Setup

1. Create `.env` from `.env.example`
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run server:

```bash
uvicorn main:app --reload
```

## Environment Variables

- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - JWT secret
- `FAL_KEY` - Fal API key (for STT/TTS)
- `OPENROUTER_API_KEY` - OpenRouter API key (for LLM)

## API Endpoints

### Auth

- POST `/api/auth/register`
- POST `/api/auth/login`

### Restaurant (Protected)

- GET `/api/restaurant/tables`
- POST `/api/restaurant/tables`
- DELETE `/api/restaurant/tables/{id}`
- GET `/api/restaurant/orders`
- PATCH `/api/restaurant/orders/{id}/status`

### Menu

- GET `/api/menu/products` (protected)
- POST `/api/menu/products` (protected)
- GET `/api/menu/{qr_token}` (public)
- POST `/api/menu/{qr_token}/checkout` (public)

### Voice WebSocket

- WS `/ws/voice/{table_id}`

## Voice Pipeline Flow

```
Mic → Audio Chunks
  ↓
STT (Freya) → Transcript
  ↓
LLM (Gemini 2.5 Flash) → Stream Tokens
  ↓
TTS (Freya) → Audio Chunks
  ↓
Speaker
```

All steps are streaming and async for ultra-low latency.
