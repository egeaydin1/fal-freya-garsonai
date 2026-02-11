# GarsonAI - Voice AI Waiter System

Real-time streaming voice AI restaurant ordering system with ultra-low latency.

## 🎯 Features

- 🎤 **Streaming STT** - Freya STT for real-time transcription
- 🧠 **Streaming LLM** - Gemini 2.5 Flash for intelligent responses
- 🔊 **Streaming TTS** - Freya TTS with Turkish voice (Zeynep)
- 🔐 **Restaurant Authentication** - JWT-based secure login
- 📱 **QR Table System** - Each table has unique QR code
- 🍽 **Menu Management** - Add/edit/remove products
- 🛒 **Real-time Cart & Orders** - Live order tracking via WebSocket
- ⚡ **Ultra-low Latency** - <2s perceived response time

## 🏗 Architecture

```
Frontend (React + Vite)
    ↓ WebSocket
Backend (FastAPI)
    ↓
Voice Pipeline:
  Audio → STT → LLM (streaming) → TTS → Audio
    ↓
PostgreSQL Database
```

## 🚀 Quick Start

### Backend Setup

1. Navigate to backend:
```bash
cd backend
```

2. Create `.env`:
```bash
cp .env.example .env
```

3. Configure `.env`:
```env
DATABASE_URL=postgresql://user:password@localhost/garsonai
SECRET_KEY=your-secret-key-change-this
FAL_KEY=your-fal-api-key
OPENROUTER_API_KEY=your-openrouter-api-key
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Run server:
```bash
uvicorn main:app --reload
```

Backend runs at: http://localhost:8000

### Frontend Setup

1. Navigate to frontend:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Run dev server:
```bash
npm run dev
```

Frontend runs at: http://localhost:5173

## 📖 Usage Guide

### For Restaurant Owners

1. **Register** at http://localhost:5173
2. **Login** to access dashboard
3. **Create Tables** - Each table gets a unique QR code
4. **Add Menu Items** - Name, price, description, category
5. **Monitor Orders** - Real-time order updates
6. **Update Status** - Mark orders as preparing/delivered/paid

### For Customers

1. **Scan QR Code** at table
2. **Browse Menu** - View available items
3. **Add to Cart** - Manual selection or...
4. **Use Voice AI** 🎤 - Talk naturally to order
   - "I'd like two pizzas"
   - "Add a cola please"
   - "What do you recommend?"
5. **Checkout** - Place order

## 🎤 Voice Pipeline

```
User speaks → Mic captures audio
    ↓
WebSocket sends audio chunks
    ↓
STT (Freya) transcribes → "iki pizza istiyorum"
    ↓
LLM (Gemini 2.5 Flash) streams response
    ↓
TTS (Freya Zeynep) converts to speech
    ↓
Audio streams back to user
```

All steps are **streaming** and **async** - no blocking!

## 🔑 API Endpoints

### Auth
- `POST /api/auth/register` - Create account
- `POST /api/auth/login` - Get JWT token

### Restaurant (Protected)
- `GET /api/restaurant/tables` - List tables
- `POST /api/restaurant/tables` - Create table
- `DELETE /api/restaurant/tables/{id}` - Delete table
- `GET /api/restaurant/orders` - List all orders
- `PATCH /api/restaurant/orders/{id}/status` - Update order status

### Menu
- `GET /api/menu/products` - List products (protected)
- `POST /api/menu/products` - Add product (protected)
- `DELETE /api/menu/products/{id}` - Delete product (protected)
- `GET /api/menu/{qr_token}` - Get public menu
- `POST /api/menu/{qr_token}/checkout` - Place order

### Voice
- `WS /ws/voice/{qr_token}` - WebSocket for voice streaming

## 🗄 Database Models

- **Restaurant** - Owner account
- **Table** - QR-linked tables
- **Product** - Menu items
- **Order** - Customer orders
- **OrderItem** - Individual order items

## 🔐 Security

- ✅ Passwords hashed with bcrypt
- ✅ JWT authentication
- ✅ API keys never exposed to frontend
- ✅ CORS configured
- ✅ Table ownership validation

## 🛠 Tech Stack

**Backend:**
- FastAPI
- SQLAlchemy + PostgreSQL
- fal-client (STT/TTS)
- OpenRouter (LLM)
- WebSockets

**Frontend:**
- React 19
- Vite
- TailwindCSS + DaisyUI
- React Router
- WebSocket API

## 📝 Development

### Run Backend with Auto-Reload
```bash
cd backend
uvicorn main:app --reload
```

### Run Frontend with HMR
```bash
cd frontend
npm run dev
```

### Database Migrations
```bash
# Auto-create tables on startup (dev mode)
# In production, use Alembic
```

## 🎯 Production Deployment

1. Set strong `SECRET_KEY` in `.env`
2. Use production database URL
3. Configure CORS origins
4. Enable HTTPS
5. Use gunicorn/uvicorn workers
6. Build frontend: `npm run build`
7. Serve frontend with nginx/vercel

## 📄 License

MIT

## 👤 Author

Built with ❤️ using GitHub Copilot
