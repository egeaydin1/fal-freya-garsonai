#!/bin/bash
# STT Latency Optimization - Quick Start

echo "🚀 STT Latency Optimization Quick Start"
echo "========================================"
echo ""

# 1. Backend yeniden başlat
echo "📦 Step 1: Restarting backend..."
echo "cd backend && python main.py"
echo ""
echo "Logs'ta şunları kontrol et:"
echo "  ✅ Container Warmer: Background task started (TTS + STT)"
echo "  🔥 TTS Warmer: Keep-alive successful"
echo "  🔥 STT Warmer: Keep-alive successful"
echo ""

# 2. Frontend build
echo "🎨 Step 2: Building frontend..."
echo "cd frontend && npm run dev"
echo ""

# 3. Test
echo "🧪 Step 3: Test scenarios"
echo ""
echo "Test 1 - Direct POST"
echo "  1. Backend logs'u izle"
echo "  2. Ses kaydı yap"
echo "  3. Kontrol et:"
echo "     ✅ 'Using direct binary POST (CDN bypass)'"
echo "     ❌ 'Direct POST failed, falling back...'"
echo ""

echo "Test 2 - Silence Trimming"
echo "  1. Browser console'u aç (F12)"
echo "  2. Ses kaydı yap (başta ve sonda biraz sessizlik bırak)"
echo "  3. Console'da kontrol et:"
echo "     📉 Original audio: XXXX bytes"
echo "     ✂️ AudioTrimmer: Trimmed XX.X%"
echo "     ✅ Final audio: XXXX bytes"
echo ""

echo "Test 3 - Container Warming"
echo "  1. İlk ses kaydını yap"
echo "  2. Backend logs'ta timing'i not et: [STT done]: XX.XXXs"
echo "  3. 15 saniye bekle"
echo "  4. İkinci kaydı yap"
echo "  5. Timing'leri karşılaştır (2. çok daha hızlı olmalı)"
echo ""

echo "📊 Expected Results"
echo "==================="
echo "Önceki:  9-10 saniye"
echo "Sonrası: 4-6 saniye ⚡"
echo ""
echo "Breakdown:"
echo "  ✅ Direct POST: -1.5 to -3s"
echo "  ✅ Silence trim: -0.6 to -1.2s"
echo "  ✅ Warm container: -2s"
echo "  ✅ Total: -4 to -6s"
echo ""

echo "📝 Değişen Dosyalar"
echo "==================="
echo "Backend:"
echo "  📄 services/stt.py - Direct multipart POST"
echo "  📄 services/tts_warmer.py - 20s interval + STT warmer"
echo ""
echo "Frontend:"
echo "  📄 utils/AudioTrimmer.js - NEW: Silence trimming"
echo "  📄 pages/VoiceAI.jsx - AudioTrimmer entegrasyonu"
echo ""

echo "✅ Setup complete! Start testing..."
