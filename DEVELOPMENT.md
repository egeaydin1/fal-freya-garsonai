# GarsonAI - Development Guide

## 🎯 System Overview

GarsonAI is a production-ready voice AI waiter system with:

- Real-time streaming voice pipeline (STT → LLM → TTS)
- Restaurant management dashboard
- QR-based table ordering system
- Live order tracking via WebSocket

## 🏗 Project Structure

```
fal-freya-garsonai/
├── backend/
│   ├── core/                 # Config, DB, Auth
│   │   ├── config.py
│   │   ├── database.py
│   │   └── auth.py
│   ├── models/               # SQLAlchemy models
│   │   └── models.py
│   ├── services/             # Voice AI services
│   │   ├── stt.py           # Freya STT
│   │   ├── tts.py           # Freya TTS
│   │   └── llm.py           # Gemini 2.5 Flash
│   ├── routers/              # API endpoints
│   │   ├── auth_routes.py
│   │   ├── restaurant_routes.py
│   │   ├── menu_routes.py
│   │   └── voice_routes.py
│   ├── websocket/            # WebSocket manager
│   │   └── manager.py
│   ├── main.py              # FastAPI app
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── ManagerDashboard.jsx
│   │   │   ├── Menu.jsx
│   │   │   └── VoiceAI.jsx
│   │   ├── services/
│   │   │   └── api.js
│   │   └── App.jsx
│   └── package.json
└── README.md
```

## 🔧 Development Workflow

### Backend Development

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your keys

# Run server (auto-reload on changes)
uvicorn main:app --reload
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Run dev server (HMR enabled)
npm run dev
```

## 🗄 Database Schema

```sql
restaurants
├── id (PK)
├── name
├── email (unique)
├── hashed_password
└── created_at

tables
├── id (PK)
├── restaurant_id (FK)
├── table_number
├── qr_token (unique)
└── is_active

products
├── id (PK)
├── restaurant_id (FK)
├── name
├── description
├── price
├── category
├── image_url
└── is_available

orders
├── id (PK)
├── restaurant_id (FK)
├── table_id (FK)
├── status (preparing/delivered/paid)
├── total_price
└── created_at

order_items
├── id (PK)
├── order_id (FK)
├── product_id (FK)
├── quantity
└── price
```

## 🔐 Authentication Flow

1. **Register/Login** → Get JWT token
2. **Store token** in localStorage
3. **Include token** in Authorization header
4. **Backend validates** token on protected routes

## 🌐 API Documentation

### Public Endpoints

- `GET /api/menu/{qr_token}` - Get menu for table
- `POST /api/menu/{qr_token}/checkout` - Place order
- `WS /ws/voice/{qr_token}` - Voice AI WebSocket

### Protected Endpoints (require JWT)

- All `/api/restaurant/*` routes
- All `/api/menu/products` CRUD routes

## 🎨 Frontend Pages

### 1. Login/Register (`/`)

- Simple auth form
- Switches between login/register
- Stores JWT on success

### 2. Manager Dashboard (`/panel`)

- **Tables Tab**: Create/delete tables, copy QR links
- **Menu Tab**: Add/edit/delete products
- **Orders Tab**: View and update order status

### 3. Menu (`/menu/{qrToken}`)

- Public menu view
- Cart management
- Manual ordering
- Voice AI button

### 4. Voice AI (`/voice/{qrToken}`)

- Microphone interface
- Real-time transcription
- Streaming AI responses
- Audio playback

## 🔊 WebSocket Protocol

### Client → Server

```javascript
// Audio chunks (binary)
ws.send(audioBlob);

// Control messages (JSON)
ws.send(JSON.stringify({ type: "ping" }));
```

### Server → Client

```javascript
// Status updates
{ type: "status", message: "processing" }

// Transcript
{ type: "transcript", text: "..." }

// AI streaming tokens
{ type: "ai_token", token: "...", full_text: "..." }

// AI complete
{ type: "ai_complete", data: {...} }

// TTS events
{ type: "tts_start" }
{ type: "tts_complete" }

// Audio chunks (binary)
<Blob>
```

## 🧪 Testing Voice Pipeline

1. Start backend: `uvicorn main:app --reload`
2. Start frontend: `npm run dev`
3. Register restaurant account
4. Create a table, copy QR link
5. Open QR link in new tab
6. Click "Voice Order" button
7. Allow microphone access
8. Speak: "I'd like a pizza"
9. Listen to AI response

## 🚀 Production Checklist

- [ ] Change `SECRET_KEY` to strong random value
- [ ] Use production PostgreSQL database
- [ ] Update CORS origins (remove `*`)
- [ ] Enable HTTPS
- [ ] Use environment variables for all secrets
- [ ] Build frontend: `npm run build`
- [ ] Deploy backend with gunicorn/uvicorn
- [ ] Set up reverse proxy (nginx)
- [ ] Configure domain and SSL
- [ ] Add rate limiting
- [ ] Set up monitoring/logging
- [ ] Database backups

## 📝 Common Tasks

### Add new API endpoint

1. Create route in `backend/routers/`
2. Add to `main.py` router includes
3. Test with curl/Postman
4. Add to frontend `services/api.js`

### Add new database model

1. Add model in `backend/models/models.py`
2. Import in `models/__init__.py`
3. Restart server (auto-creates tables)

### Modify voice pipeline

1. Edit `backend/services/stt.py|tts.py|llm.py`
2. Update `backend/routers/voice_routes.py` flow
3. Test via WebSocket

## 🐛 Troubleshooting

**Database connection error:**

- Check PostgreSQL is running
- Verify DATABASE_URL in .env

**Voice not working:**

- Check FAL_KEY and OPENROUTER_API_KEY
- Verify microphone permissions
- Check WebSocket connection in browser console

**CORS errors:**

- Backend and frontend must run on different ports
- Check CORS middleware in main.py

## 📚 Resources

- FastAPI: https://fastapi.tiangolo.com
- Fal.ai: https://fal.ai/docs
- React Router: https://reactrouter.com
- DaisyUI: https://daisyui.com
