# 🚀 STT Latency Optimization Report

**Tarih:** 12 Şubat 2026  
**Hedef:** Whisper inference süresini değiştirmeden toplam STT latency'sini azaltmak  
**Sonuç:** 9-10 saniye → **4-6 saniye** (beklenen)

---

## 📊 Problem Analizi

Önceki loglardan:

```
[STT done]: 09.6s
```

Bu süre **sadece inference değil**, şunların toplamı:

| Bileşen | Tahmini Süre | Kontrol Edilebilir? |
|---------|--------------|---------------------|
| **Upload (CDN)** | 1.5-3s | ✅ Evet |
| **Queue wait** | 0.5-2s | ✅ Kısmen (warmer ile) |
| **Cold start** | 2-3s | ✅ Evet (warmer) |
| **Inference** | 1-2s | ❌ Hayır (model sabit) |
| **Network RTT** | 0.1-0.5s | ✅ Kısmen (region) |

**Toplam:** ~6-11 saniye

**Kritik Fark:** Inference süresi sadece 1-2 saniye! Geri kalan 7-8 saniye orchestration overhead.

---

## ✅ Uygulanan Optimizasyonlar

### 1. 🎯 Direct Binary POST (CDN Bypass)

**Önceki Akış:**
```
1. audio_bytes → temp file yaz
2. fal_client.upload_file() → CDN'e upload
3. CDN URL döner
4. fal_client.subscribe(audio_url=cdn_url)
5. Container CDN'den dosyayı indirir
6. Inference başlar
```

**Toplam:** ~3-5 saniye overhead

**Yeni Akış:**
```
1. audio_bytes → multipart/form-data
2. httpx.post(files={"audio": bytes})
3. Inference hemen başlar
```

**Kazanç:** 1.5-3 saniye ⚡

**Kod:**
```python
# backend/services/stt.py
files = {
    "audio": ("audio.webm", io.BytesIO(audio_data), "audio/webm")
}

response = await self.http_client.post(
    self.api_url,
    files=files,
    data={
        "task": "transcribe",
        "language": "tr",
        "chunk_level": "segment"
    },
    headers={"Authorization": f"Key {settings.FAL_KEY}"}
)
```

**Not:** Eğer fal API multipart desteklemiyorsa, fallback olarak eski yöntem kullanılır.

---

### 2. ✂️ Silence Trimming

**Sorun:** Kullanıcı konuştuktan sonra:
- Başta 200ms sessizlik
- Sonda 1-2 saniye sessizlik

Whisper bu sessizlikleri de işliyor → gereksiz inference süresi.

**Çözüm:** Frontend'te RMS analizi ile sessizlikleri kes.

**Kod:**
```javascript
// frontend/src/utils/AudioTrimmer.js
const startIndex = this._findFirstNonSilence(channelData, sampleRate);
const endIndex = this._findLastNonSilence(channelData, sampleRate);
```

**Örnek:**
- Orijinal: 4 saniye audio (1s sessizlik + 2s konuşma + 1s sessizlik)
- Trimmed: 2.2 saniye audio (0.1s padding + 2s konuşma + 0.1s padding)

**Kazanç:** %30-40 daha hızlı inference (~0.6-1.2 saniye)

**Entegrasyon:**
```javascript
// VoiceAI.jsx
const trimmedBlob = await trimmerRef.current.trimSilence(fullAudioBlob);
const compressedBlob = await compressorRef.current.compressAudio(trimmedBlob);
wsRef.current.send(compressedBlob);
```

---

### 3. 🔥 Aggressive Container Warming

**Önceki:**
- TTS warmer: 30 saniye interval
- STT warmer: yok

**Sorun:** fal container idle timeout ~60-120 saniye
- 30s interval → bazı istekler cold start yaşıyor
- STT her zaman cold start

**Yeni:**
```python
# backend/services/tts_warmer.py
def __init__(self, interval: int = 20):  # 30s → 20s

async def run(self):
    await asyncio.gather(
        self.warmup_tts(),    # TTS container
        self.warmup_stt(),    # STT container (YENİ!)
        return_exceptions=True
    )
```

**Kazanç:** Cold start 2-3s → 0-0.5s (~2 saniye) ⚡

**Maliyet:** Her 20 saniyede 2 test API çağrısı (minimal)

---

### 4. ⚡ Parallel Processing (Zaten Mevcut)

WebSocket handler'da zaten paralel TTS var:

```python
# İlk cümle tamamlanınca TTS başlatılıyor
if first_sentence_complete:
    tts_task = asyncio.create_task(stream_tts_parallel())
```

Bu sayede LLM devam ederken TTS başlıyor.

**Not:** STT için parallelization şu an gerekli değil çünkü STT tek seferde yapılıyor.

---

### 5. 📊 Enhanced Logging

**Yeni loglar:**

```python
# Detaylı timing breakdown
print(f"📡 STT: HTTP request took {t_response - t_request:.3f}s")
print(f"✅ [STT done]: {elapsed:06.3f}s total | {request_time:.3f}s request")
print(f"✅ [STT done]: {elapsed:06.3f}s total | upload: {upload_time:.3f}s | inference: {inference_time:.3f}s")
```

Bu sayede hangi aşamada problem olduğu net görünüyor.

---

## 📈 Beklenen Sonuçlar

### Önceki Timing:
```
[00:00.000] Audio received
[00:03.500] Upload complete
[00:05.500] Queue start (cold container)
[00:09.600] STT complete ❌
```

### Yeni Timing (Best Case):
```
[00:00.000] Audio received
[00:00.100] Trimming complete (-40% audio)
[00:00.200] Direct POST start
[00:00.500] Inference start (warm container)
[00:01.500] Inference complete (1s audio)
[00:01.600] STT complete ✅
```

### Yeni Timing (Realistic):
```
[00:00.000] Audio received
[00:00.150] Trimming complete (-30% audio)
[00:00.250] Direct POST start
[00:01.000] Inference start (warm/cold mix)
[00:02.500] Inference complete (1.5s audio)
[00:02.700] STT complete ✅
```

**Toplam:** 4-6 saniye (önceki: 9-10 saniye)

---

## 🎯 Region Kontrolü (Manuel)

fal.ai dashboard'dan kontrol et:

1. https://fal.ai/dashboard → Settings
2. Default region nedir?
   - US-East (Virginia) ✅ En hızlı
   - EU-West (Frankfurt) ⚠️ +50-100ms
   - AP-Southeast (Singapore) ❌ +200-300ms

3. Eğer EU region kullanılıyorsa:
   - Latency: +100-200ms
   - Değiştirilebilir mi? → fal API docs kontrol et

---

## 🔬 Test Senaryoları

### Test 1: Direct POST vs CDN Upload
```bash
# Backend logs'u izle
tail -f backend.log

# Frontend'ten ses kaydı yap (3 saniye konuşma)
# Loglarda ara:
✅ "Using direct binary POST (CDN bypass)" → Direct POST çalışıyor
⚠️ "Direct POST failed, falling back..." → Fallback'e düştü
```

**Beklenen:** Direct POST başarılı olmalı

### Test 2: Silence Trimming Etkisi
```javascript
// Browser console'da kontrol et
📉 Original audio: 35000 bytes
✂️ AudioTrimmer: Trimmed 35.2% (3.50s → 2.27s)
✅ Final audio: 22000 bytes
```

**Beklenen:** %20-40 reduction

### Test 3: Container Warm/Cold
```bash
# İlk istek (container cold)
[STT done]: 05.200s total | 3.800s request

# 15 saniye sonra ikinci istek (container warm)
[STT done]: 02.100s total | 0.900s request ✅
```

**Beklenen:** 2. istek çok daha hızlı

---

## ⚠️ Bilinen Sınırlamalar

### 1. fal API Multipart Desteği Belirsiz
Eğer fal API direct multipart desteklemiyorsa:
- Fallback: CDN upload (eski yöntem)
- Test gerekli

**Alternatif:**
```python
# Base64 encoding (daha yavaş ama CDN'siz)
audio_b64 = base64.b64encode(audio_data).decode('utf-8')
```

### 2. AudioTrimmer Performance
Browser'da AudioContext decoding:
- 3 saniyelik audio: ~50-100ms overhead
- 10 saniyelik audio: ~200-300ms overhead

**Çözüm:** Acceptable trade-off (inference kazancı > decoding overhead)

### 3. Warmer Maliyeti
Her 20 saniyede 2 API call:
- Günlük: 2 * 3 * 60 * 24 = 8,640 call
- Aylık: ~260,000 call

**Optimizasyon:**
- Sadece aktif saatlerde çalıştır
- Veya interval'i 30s'e geri çek

---

## 🚀 Gelecek Optimizasyonlar

### 1. Segment-based Pseudo Streaming
Kullanıcı konuşurken her 1 saniyede bir segment gönder:

```javascript
// Her 1 saniyede bir STT çağrısı
setInterval(() => {
    if (isRecording && audioChunks.length > 0) {
        sendPartialAudio();  // Partial transcription
    }
}, 1000);
```

**Kazanç:** Kullanıcı konuşurken STT başlar (~2-3s)

**Zorluk:** fal API partial result destekliyor mu?

### 2. Edge Computing
CDN yerine Cloudflare Workers'da STT:
- RTT: <50ms
- Ama Whisper çalıştıramaz

**Alternatif:** WebAssembly Whisper (browser'da)
- https://github.com/ggerganov/whisper.cpp
- WASM build → browser'da inference
- Latency: <1s ⚡⚡⚡

### 3. Custom Model Deployment
Kendi Whisper container'ı:
- fal.ai yerine kendi sunucusu
- Warm container 7/24
- Region control

**Maliyet:** ~$50-100/ay

---

## 📝 Özet

| Optimizasyon | Kazanç | Zorluk | Durum |
|-------------|--------|--------|-------|
| Direct Binary POST | 1.5-3s | Orta | ✅ Uygulandı |
| Silence Trimming | 0.6-1.2s | Düşük | ✅ Uygulandı |
| Aggressive Warmer | ~2s | Düşük | ✅ Uygulandı |
| Region Optimization | 0.1-0.2s | Düşük | ⚠️ Manuel kontrol |
| Enhanced Logging | - | Düşük | ✅ Uygulandı |

**Toplam Beklenen Kazanç:** 4-6 saniye

**Önceki:** 9-10 saniye  
**Sonrası:** 4-6 saniye ⚡

---

## 🧪 Test Checklist

- [ ] Backend'i yeniden başlat
- [ ] Frontend build et
- [ ] İlk test: Cold start timing
- [ ] İkinci test (20s sonra): Warm container timing
- [ ] Browser console'da trimming loglarını kontrol et
- [ ] Backend'de "Direct POST" veya "fallback" mesajını kontrol et
- [ ] Timing breakdown'ları karşılaştır

---

## 📞 Troubleshooting

### "Direct POST failed" Mesajı
**Sebep:** fal API multipart desteklemiyor  
**Çözüm:** Fallback CDN upload kullanılacak (yine de warmer + trimming kazancı var)

### Trimming %10'dan Az
**Sebep:** Kullanıcı hemen konuşup hemen bitiyor  
**Çözüm:** Normal, sessizlik zaten az

### Warmer Çalışmıyor
**Sebep:** Backend restart gerekli  
**Çözüm:**
```bash
cd backend
python main.py
# Logs'ta şunu ara:
# ✅ Container Warmer: Background task started (TTS + STT)
```

---

**Son Güncelleme:** 12 Şubat 2026  
**Yazan:** AI Assistant  
**Versiyon:** 2.0
