# GarsonAI Backend API Dokümantasyonu

## Genel Bakış

GarsonAI backend, FastAPI ile geliştirilmiş bir sesli asistan API'sidir. Frontend uygulamaları için iki ana endpoint sağlar:

1. **Chat Başlatma** - Kullanıcı metnini gönder, task ID al
2. **Streaming Cevap** - NDJSON formatında stream olarak AI cevabı ve ses segmentleri al

## 🚀 Backend'i Başlatma

```bash
cd backend
python main.py
```

**Varsayılan Port:** `http://localhost:8000`

## 📡 API Endpoints

### 1. Chat Başlatma

Kullanıcının metinini gönderir ve işlem için bir task ID alır.

**Endpoint:**
```
POST /api/ai/chat-text
```

**Request Body:**
```json
{
  "text": "Merhaba, menüde ne var?"
}
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "started"
}
```

**cURL Örneği:**
```bash
curl -X POST http://localhost:8000/api/ai/chat-text \
  -H "Content-Type: application/json" \
  -d '{"text": "Merhaba, menüde ne var?"}'
```

**JavaScript Fetch Örneği:**
```javascript
const response = await fetch('http://localhost:8000/api/ai/chat-text', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    text: 'Merhaba, menüde ne var?'
  })
});

const data = await response.json();
console.log('Task ID:', data.task_id);
```

---

### 2. Streaming Cevap

Task ID ile AI cevabını ve ses segmentlerini stream olarak alır.

**Endpoint:**
```
GET /api/ai/stream/{task_id}
```

**Content-Type:** `application/x-ndjson` (Newline Delimited JSON)

**Stream Event Türleri:**

#### Event 1: AI Cevabı
```json
{
  "type": "ai_response",
  "data": "Merhaba! Menümüzde pizza, makarna ve salatalar var."
}
```

#### Event 2: Ses Segmenti
```json
{
  "type": "audio_segment",
  "data": {
    "index": 0,
    "text": "Merhaba!",
    "audio_url": "https://example.com/audio/segment_0.mp3"
  }
}
```

#### Event 3: Tamamlandı
```json
{
  "type": "complete"
}
```

#### Event 4: Hata
```json
{
  "type": "error",
  "data": "Bir hata oluştu"
}
```

**cURL Örneği:**
```bash
curl http://localhost:8000/api/ai/stream/550e8400-e29b-41d4-a716-446655440000
```

**JavaScript Fetch + ReadableStream Örneği:**
```javascript
const taskId = '550e8400-e29b-41d4-a716-446655440000';
const response = await fetch(`http://localhost:8000/api/ai/stream/${taskId}`);

const reader = response.body.getReader();
const decoder = new TextDecoder();
let buffer = '';

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  buffer += decoder.decode(value, { stream: true });
  const lines = buffer.split('\n');
  buffer = lines.pop() || '';

  for (const line of lines) {
    if (line.trim()) {
      const event = JSON.parse(line);
      
      switch (event.type) {
        case 'ai_response':
          console.log('AI Cevabı:', event.data);
          break;
        
        case 'audio_segment':
          console.log('Ses Segmenti:', event.data);
          // Audio player'a ekle
          break;
        
        case 'complete':
          console.log('Stream tamamlandı');
          break;
        
        case 'error':
          console.error('Hata:', event.data);
          break;
      }
    }
  }
}
```

## 🔄 Tam İş Akışı

### 1. Kullanıcı Konuşur
Frontend'de ses kaydı yapılır ve metne çevrilir (STT - Speech to Text).

### 2. Backend'e Metin Gönderilir
```javascript
const startResponse = await fetch('/api/ai/chat-text', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ text: userSpeechText })
});

const { task_id } = await startResponse.json();
```

### 3. Stream Açılır
```javascript
const streamResponse = await fetch(`/api/ai/stream/${task_id}`);
const reader = streamResponse.body.getReader();
```

### 4. Event'ler İşlenir
```javascript
// NDJSON stream'i parse et
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  
  // Her satır bir JSON event'i
  const event = parseNDJSONLine(value);
  
  if (event.type === 'ai_response') {
    // Tam AI cevabını göster
    displayAIResponse(event.data);
  }
  
  if (event.type === 'audio_segment') {
    // Ses segmentini oynat
    playAudioSegment(event.data.audio_url);
  }
  
  if (event.type === 'complete') {
    // İşlem tamamlandı
    break;
  }
}
```

## 📊 Stream Akış Şeması

```
Frontend                          Backend
   |                                 |
   |  POST /chat-text               |
   |  { text: "..." }               |
   |------------------------------>  |
   |                                 |
   |  { task_id, status }           |
   |<------------------------------  |
   |                                 |
   |  GET /stream/{task_id}         |
   |------------------------------>  |
   |                                 |
   |  Stream başlıyor...            |
   |                                 |
   |  {"type":"ai_response"...}     |
   |<------------------------------  |
   |                                 |
   |  {"type":"audio_segment"...}   |
   |<------------------------------  |
   |                                 |
   |  {"type":"audio_segment"...}   |
   |<------------------------------  |
   |                                 |
   |  {"type":"complete"}           |
   |<------------------------------  |
   |                                 |
```

## 🎯 Önemli Noktalar

### 1. **NDJSON Format**
- Her satır ayrı bir JSON objesi
- Satırlar `\n` (newline) ile ayrılır
- Progressive parsing yapılabilir

### 2. **Stream Sırası**
1. Önce `ai_response` gelir (tam metin)
2. Sonra `audio_segment` event'leri gelir (sırayla)
3. En son `complete` event'i gelir

### 3. **Audio Segment Yönetimi**
- `index` alanı segmentlerin sırasını gösterir
- Segmentler sırayla oynatılmalı
- Üst üste binmemeli (queue kullan)

### 4. **Error Handling**
```javascript
if (event.type === 'error') {
  console.error('Backend hatası:', event.data);
  // Kullanıcıya göster
  showErrorToast(event.data);
}
```

## 🔧 Backend Konfigürasyonu

**Port:** 8000 (varsayılan)
**CORS:** Tüm originler için açık
**Timeout:** Stream için 30 saniye

## 🧪 Test Etme

### Manuel Test (cURL)

```bash
# 1. Chat başlat
TASK_ID=$(curl -s -X POST http://localhost:8000/api/ai/chat-text \
  -H "Content-Type: application/json" \
  -d '{"text":"Merhaba"}' | jq -r '.task_id')

echo "Task ID: $TASK_ID"

# 2. Stream'i izle
curl http://localhost:8000/api/ai/stream/$TASK_ID
```

### Postman ile Test

1. **POST** isteği: `http://localhost:8000/api/ai/chat-text`
   - Body → raw → JSON
   - ```{"text": "Merhaba"}```
   - task_id'yi kopyala

2. **GET** isteği: `http://localhost:8000/api/ai/stream/{task_id}`
   - Response'da NDJSON stream'i görürsün

## 📝 TypeScript Tip Tanımları

```typescript
// Request tipleri
interface ChatStartRequest {
  text: string;
}

interface ChatStartResponse {
  task_id: string;
  status: string;
}

// Stream event tipleri
type StreamEventType = 'ai_response' | 'audio_segment' | 'complete' | 'error';

interface StreamEvent {
  type: StreamEventType;
  data?: any;
}

interface AudioSegment {
  index: number;
  text: string;
  audio_url: string;
}

interface AIResponseEvent {
  type: 'ai_response';
  data: string;
}

interface AudioSegmentEvent {
  type: 'audio_segment';
  data: AudioSegment;
}

interface CompleteEvent {
  type: 'complete';
}

interface ErrorEvent {
  type: 'error';
  data: string;
}
```

## 🐛 Yaygın Hatalar ve Çözümler

### Hata 1: "Task not found"
**Sebep:** Geçersiz task_id veya timeout
**Çözüm:** task_id'yi doğru kullan, stream'i hemen aç

### Hata 2: Stream kesilmesi
**Sebep:** Network timeout veya backend hatası
**Çözüm:** Retry mekanizması ekle, error event'ini handle et

### Hata 3: CORS hatası
**Sebep:** Frontend farklı domain'de çalışıyor
**Çözüm:** Backend CORS ayarları açık, proxy kullan

## 💡 Best Practices

### 1. Retry Mekanizması
```javascript
async function startChatWithRetry(text, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const response = await fetch('/api/ai/chat-text', {
        method: 'POST',
        body: JSON.stringify({ text })
      });
      return await response.json();
    } catch (err) {
      if (i === maxRetries - 1) throw err;
      await new Promise(r => setTimeout(r, 1000 * (i + 1)));
    }
  }
}
```

### 2. Timeout Yönetimi
```javascript
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 30000);

try {
  const response = await fetch('/api/ai/chat-text', {
    signal: controller.signal,
    // ...
  });
} finally {
  clearTimeout(timeoutId);
}
```

### 3. Buffer Yönetimi
```javascript
let buffer = '';

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  buffer += decoder.decode(value, { stream: true });
  const lines = buffer.split('\n');
  
  // Son satırı buffer'da tut (eksik olabilir)
  buffer = lines.pop() || '';

  // Tam satırları işle
  for (const line of lines) {
    if (line.trim()) {
      const event = JSON.parse(line);
      handleEvent(event);
    }
  }
}

// Kalan buffer'ı işle
if (buffer.trim()) {
  const event = JSON.parse(buffer);
  handleEvent(event);
}
```

## 📚 Ek Kaynaklar

- **FastAPI Dokümantasyonu:** http://localhost:8000/docs
- **NDJSON Spec:** http://ndjson.org/
- **Stream API:** https://developer.mozilla.org/en-US/docs/Web/API/Streams_API

## 🎓 Özet Checklist

Frontend geliştiricisi için:

- [ ] Backend'i `python main.py` ile başlat
- [ ] POST `/api/ai/chat-text` ile task_id al
- [ ] GET `/api/ai/stream/{task_id}` ile stream aç
- [ ] NDJSON formatını parse et (satır satır)
- [ ] `ai_response` event'inde metni göster
- [ ] `audio_segment` event'lerini queue'ya ekle
- [ ] Segmentleri sırayla oynat (overlap olmasın)
- [ ] `complete` event'inde temizlik yap
- [ ] `error` event'inde kullanıcıya bildir
- [ ] Timeout ve retry mekanizması ekle

---

**Backend Hazır! Frontend entegrasyonunda başarılar! 🚀**

Sorular için: Backend kodları `/backend` klasöründe
