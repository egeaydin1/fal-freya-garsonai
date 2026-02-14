# ========== Stage 1: Frontend build ==========
FROM node:22-alpine AS frontend-build

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ .

# Railway: set these in Dashboard → Variables (or use RAILWAY_PUBLIC_DOMAIN)
ARG VITE_API_URL
ARG VITE_WS_URL
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_WS_URL=${VITE_WS_URL}

RUN npm run build

# ========== Stage 2: Backend + static frontend ==========
FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Backend code
COPY backend/ .

# Frontend build (from stage 1)
COPY --from=frontend-build /app/frontend/dist ./static

# Railway sets PORT at runtime
ENV PORT=8000
EXPOSE 8000

# Gunicorn binds to 0.0.0.0:${PORT} for Railway
CMD gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind "0.0.0.0:${PORT}"
