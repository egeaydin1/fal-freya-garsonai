# 🎤 GarsonAI - Sesli Sipariş Asistanı

Hackathon 2026 projesi - Restoranlarda sesli sipariş alma için AI destekli asistan

## 🎯 Proje Hakkında

GarsonAI, restoran müşterilerinin QR kod okutarak sesli olarak sipariş vermelerini sağlayan yapay zeka destekli bir uygulamadır. Alerjen kontrolü, ürün önerisi ve doğal dil işleme ile müşteri deneyimini optimize eder.

**Magic Moment:** Müşteri masaya oturur, QR kodu okuttur ve 30 saniye içinde siparişini tamamlar - garson çağırmadan!

## 📚 Dökümanlar

- **[Hackathon Başvurusu](./HACKATHON_APPLICATION.md)** - Detaylı proje açıklaması, teknik detaylar ve başarı metrikleri
- **[Teknik Mimari](./TECHNICAL_ARCHITECTURE.md)** - Sistem mimarisi, bileşenler ve API detayları
- **[48 Saat Timeline](./IMPLEMENTATION_TIMELINE.md)** - Saat-saat implementasyon planı

## ✨ Özellikler

- 🎤 **Sesli Sipariş:** Doğal dil ile sipariş verme
- 🚨 **Alerjen Kontrolü:** Otomatik alerjen taraması ve uyarıları
- 🤖 **Akıllı Öneriler:** AI destekli ürün önerileri
- ⚡ **Düşük Gecikme:** İlk ses yanıtı < 400ms
- 📊 **Admin Panel:** Gerçek zamanlı sipariş takibi

## 🛠️ Teknoloji Yığını

### AI Services
- **STT:** Freya AI Speech-to-Text (Türkçe optimize)
- **LLM:** Gemini 2.5 Flash (ana), GPT-4o-mini (yedek)
- **TTS:** Freya AI Text-to-Speech (doğal Türkçe)

### Frontend
- Next.js 14+ (App Router)
- React Hooks
- TailwindCSS
- Web Audio API

### Backend
- FastAPI (Python 3.11+)
- Uvicorn (ASGI server)
- Supabase/Firebase (Database)

### Deployment
- Frontend: Vercel
- Backend: Railway
- CDN: CloudFlare (audio cache)

## 🚀 Kurulum

### Gereksinimler
- Node.js 18+
- Python 3.11+
- npm veya yarn
- Git

### 1. Repository Clone
```bash
git clone https://github.com/[your-org]/fal-freya-garsonai.git
cd fal-freya-garsonai
```

### 2. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# .env dosyası oluştur
cp .env.example .env
# API keylerini doldur
```

### 3. Frontend Setup
```bash
cd frontend
npm install

# .env.local dosyası oluştur
cp .env.example .env.local
# Backend URL'i ayarla
```

### 4. Database Setup
```bash
# Supabase dashboard'dan proje oluştur
# SQL dosyasını çalıştır
psql -h [supabase-host] -U postgres -f database/schema.sql
```

### 5. Çalıştırma

**Backend:**
```bash
cd backend
uvicorn main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm run dev
```

**Uygulama:** http://localhost:3000

## 📱 Kullanım

1. Ana sayfadan QR kodu tarat
2. Mikrofon izni ver
3. "I'm listening..." göründüğünde konuşmaya başla
4. AI ile sohbet ederek sipariş ver
5. Siparişi onayla
6. Admin panel'den siparişi gör

## 🧪 Test

```bash
# Backend testleri
cd backend
pytest

# Frontend testleri
cd frontend
npm test
```

## 📈 Performans Metrikleri

| Metrik | Hedef | Gerçek |
|--------|-------|--------|
| İlk ses latency | < 400ms | TBD |
| Tam yanıt süresi | < 2s | TBD |
| Alerjen doğruluğu | 100% | TBD |

## 🤝 Takım

**GarsonAI Team**
- [Ekip üyesi 1]
- [Ekip üyesi 2]
- [Ekip üyesi 3]

## 📄 Lisans

MIT License - Hackathon 2026

## 🙏 Teşekkürler

- Freya AI - STT/TTS API
- Google Gemini - LLM API
- Hackathon organizatörleri

---

**Proje Durumu:** 🏗️ Development  
**Hackathon:** 2026  
**Son Güncelleme:** 10 Şubat 2026
