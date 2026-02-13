#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Shutting down...${NC}"
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
    wait 2>/dev/null
    echo -e "${GREEN}✅ All processes stopped.${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM

# ── Pre-checks ──────────────────────────────────────────────
echo -e "${CYAN}🚀 GarsonAI Startup${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# .env check
if [ ! -f "$BACKEND/.env" ]; then
    echo -e "${RED}❌ backend/.env not found!${NC}"
    echo "   Create it with: DATABASE_URL, SECRET_KEY, FAL_KEY, OPENROUTER_API_KEY"
    exit 1
fi
echo -e "${GREEN}✔${NC} .env found"

# Kill anything already on ports 8000 / 5173-5180
for PORT in 8000 5173 5174 5175 5176 5177 5178 5179 5180; do
    lsof -ti :"$PORT" 2>/dev/null | xargs kill -9 2>/dev/null || true
done

# ── Backend setup ───────────────────────────────────────────
echo ""
echo -e "${CYAN}📦 Backend${NC}"

if [ ! -d "$BACKEND/venv" ]; then
    echo "   Creating virtual environment..."
    python3 -m venv "$BACKEND/venv"
fi

source "$BACKEND/venv/bin/activate"
echo -e "${GREEN}✔${NC} venv activated ($(python3 --version))"

# Install deps quietly
echo "   Installing dependencies..."
pip install -r "$BACKEND/requirements.txt" -q 2>&1 | tail -1
echo -e "${GREEN}✔${NC} Dependencies installed"

# Start backend
cd "$BACKEND"
uvicorn main:app --reload \
    --reload-exclude 'venv/*' \
    --reload-exclude '__pycache__/*' \
    --reload-exclude '*.db' \
    --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd "$ROOT"

# Wait for backend to be ready
echo -n "   Waiting for backend"
for i in $(seq 1 30); do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo ""
        echo -e "${GREEN}✔${NC} Backend running → http://localhost:8000"
        break
    fi
    echo -n "."
    sleep 1
done

if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo ""
    echo -e "${RED}❌ Backend failed to start. Check logs above.${NC}"
    kill "$BACKEND_PID" 2>/dev/null
    exit 1
fi

# ── Frontend setup ──────────────────────────────────────────
echo ""
echo -e "${CYAN}📦 Frontend${NC}"

if [ ! -d "$FRONTEND/node_modules" ]; then
    echo "   Installing npm packages..."
    cd "$FRONTEND" && npm install --silent 2>&1 | tail -1
    cd "$ROOT"
fi
echo -e "${GREEN}✔${NC} node_modules ready"

cd "$FRONTEND"
npm run dev &
FRONTEND_PID=$!
cd "$ROOT"

# Wait for frontend
sleep 3
echo -e "${GREEN}✔${NC} Frontend running → http://localhost:5173"

# ── Ready ───────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}🎉 GarsonAI is ready!${NC}"
echo ""
echo -e "   ${CYAN}Backend${NC}  → http://localhost:8000"
echo -e "   ${CYAN}Frontend${NC} → http://localhost:5173"
echo -e "   ${CYAN}API Docs${NC} → http://localhost:8000/docs"
echo ""
echo -e "   Press ${YELLOW}Ctrl+C${NC} to stop everything"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

wait
