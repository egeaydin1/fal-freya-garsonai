# ⚡ GarsonAI — Latency Optimizasyonları

> Ses yakalama → transport → STT → LLM → TTS → oynatma pipeline'ının her aşamasında uygulanan **35+ optimizasyon** tekniği.

---

## 📊 Genel Sonuç

```
ÖNCESİ (Sequential Pipeline):
  Ses: 40KB stereo, 48kHz, 32kbps
  VAD: 1.5s sessizlik eşiği
  STT: Tüm kaydı bekle, sonra işle
  Pipeline: Sıralı (STT → bekle → LLM → bekle → TTS)
  Ağ: HTTP REST, blocking çağrılar
  Toplam latency: 5-7 saniye

SONRASI (Full-Duplex Incremental):
  Ses: 12-15KB mono, 16kHz, 16kbps  (-70% boyut!) ✅
  VAD: 800ms sessizlik eşiği        (-700ms) ✅
  STT: Incremental (konuşurken işle) ⚡
  Pipeline: Paralel (LLM ∥ TTS overlap) (-1-2s) ✅
  Ağ: WebSocket binary, uvloop       (-300ms) ✅
  Dayanıklılık: Retry logic + rate limiting ✅
  Toplam latency: 2.5-4s ideal (50-60% daha hızlı!) 🚀
```

---

## 1. 🎤 Ses Yakalama Optimizasyonları

### 1.1 Mono Kanal Kaydı

**Dosya:** `frontend/src/pages/VoiceAI.jsx`, `frontend/src/pages/Menu.jsx`

```js
const stream = await navigator.mediaDevices.getUserMedia({
  audio: {
    channelCount: 1, // Mono — stereo değil
    sampleRate: 16000, // 16kHz
  },
});
```

|              | Stereo | Mono                 |
| ------------ | ------ | -------------------- |
| Kanal sayısı | 2      | 1                    |
| Veri boyutu  | 2x     | 1x                   |
| **Kazanç**   | —      | **%50 daha az veri** |

### 1.2 16kHz Örnekleme Oranı

```js
sampleRate: 16000; // 16kHz — STT'nin native oranı
```

|                     | 48kHz (varsayılan) | 16kHz                                           |
| ------------------- | ------------------ | ----------------------------------------------- |
| Saniye başına örnek | 48.000             | 16.000                                          |
| **Kazanç**          | —                  | **3x daha az veri, yeniden örnekleme gerekmez** |

### 1.3 Ultra-Düşük Bitrate (16kbps Opus)

**Dosya:** `frontend/src/pages/VoiceAI.jsx`, `frontend/src/pages/Menu.jsx`

```js
const mediaRecorder = new MediaRecorder(stream, {
  mimeType: "audio/webm;codecs=opus",
  audioBitsPerSecond: 16000, // 16kbps — ses için yeterli
});
```

|               | 128kbps (típik) | 16kbps                  |
| ------------- | --------------- | ----------------------- |
| Saniyede veri | ~16 KB/s        | ~2 KB/s                 |
| **Kazanç**    | —               | **8x daha küçük dosya** |

### 1.4 Tarayıcı Ses İşleme

```js
echoCancellation: true,   // Eko iptali
noiseSuppression: true,   // Gürültü bastırma
autoGainControl: true     // Otomatik kazanç
```

**Etki:** Sunucu tarafında ek işleme gerektirmeden STT doğruluğunu artırır.

### 1.5 AudioCompressor Yardımcı Sınıfı

**Dosya:** `frontend/src/utils/AudioCompressor.js`

```js
// Stereo → mono dönüşümü + 16kHz yeniden örnekleme + 16kbps Opus yeniden kodlama
// Sonuç: %30-40 ek boyut azaltma
```

---

## 2. 📡 Streaming / Chunk Stratejileri

### 2.1 500ms Chunk Streaming

**Dosya:** `frontend/src/pages/VoiceAI.jsx`, `frontend/src/pages/Menu.jsx`

```js
// Her 500ms'de bir ondataavailable tetikleniyor
mediaRecorder.start(500);

// Her chunk anında WebSocket'e binary olarak gönderiliyor
recorder.ondataavailable = async (e) => {
  const arrayBuffer = await e.data.arrayBuffer();
  wsRef.current.send(arrayBuffer); // Konuşma bitmeden sürekli
};
```

**Etki:** Ses 500ms aralıklarla sunucuya akar — tüm kaydın bitmesi beklenmez. Kullanıcı konuşurken eş zamanlı STT işleme başlar.

### 2.2 Incremental/Partial STT İşleme

**Dosya:** `backend/routers/voice_routes.py`, `backend/websocket/voice_session.py`

```python
MIN_CHUNK_DURATION: float = 1.2  # 1.2s yeterli audio biriktiğinde işle

def can_process_partial_stt(self) -> bool:
    buffer_duration = len(self.audio_buffer) / (16000 * 2)
    time_since_last = time.time() - self.last_stt_process_time
    return (
        buffer_duration >= self.MIN_CHUNK_DURATION and
        time_since_last >= self.MIN_CHUNK_DURATION
    )
```

**Etki:** Kullanıcı henüz konuşurken STT çalışır → canlı transkript gösterilir.

### 2.3 Audio Buffer Overlap (Bağlam Sürekliliği)

**Dosya:** `backend/websocket/voice_session.py`

```python
def clear_processed_audio(self, keep_overlap: bool = True):
    if keep_overlap:
        overlap_size = 8000  # Son 500ms'i tut (16kHz, 16-bit)
        if len(self.audio_buffer) > overlap_size:
            self.audio_buffer = bytearray(self.audio_buffer[-overlap_size:])
```

**Etki:** Chunk'lar arası akustik bağlam korunur → daha doğru STT.

### 2.4 Buffer Taşma Koruması

```python
MAX_BUFFER_SIZE: int = 1024 * 1024  # 1MB max

if len(self.audio_buffer) > self.MAX_BUFFER_SIZE:
    self.audio_buffer = bytearray(self.audio_buffer[-500000:])  # Son 500KB'ı tut
```

---

## 3. 🔇 VAD (Ses Aktivite Algılama)

### 3.1 Agresif 800ms Sessizlik Eşiği

**Dosya:** `frontend/src/utils/VoiceActivityDetector.js`

```js
this.silenceThreshold = 0.01; // Amplitüd eşiği (%1)
this.silenceDuration = 800; // 800ms — agresif eşik
```

|                | Tipik (1500ms) | Bizim (800ms)                  |
| -------------- | -------------- | ------------------------------ |
| Bekleme süresi | 1.5s           | 0.8s                           |
| **Kazanç**     | —              | **700ms daha hızlı auto-stop** |

### 3.2 100ms VAD Yoklama Aralığı

```js
vadIntervalRef.current = setInterval(() => {
  const vadStatus = vadRef.current.analyzeAudioLevel();
  if (vadStatus === "SILENCE_DETECTED") {
    stopListening();
  }
}, 100); // Her 100ms'de kontrol
```

**Etki:** Sessizlik max 100ms gecikmeyle algılanır.

### 3.3 Hafif RMS Tabanlı Analiz

```js
analyzeAudioLevel() {
  this.analyser.getByteTimeDomainData(this.dataArray);
  let sum = 0;
  for (let i = 0; i < this.dataArray.length; i++) {
    const normalized = (this.dataArray[i] - 128) / 128;
    sum += normalized * normalized;
  }
  const rms = Math.sqrt(sum / this.dataArray.length);
}
```

**Etki:** CPU'ya yük bindirmeyen basit matematiksel hesaplama — ML modeli gerekmez.

### 3.4 Güvenlik Zaman Aşımı (12s)

```js
setTimeout(() => {
  if (mediaRecorderRef.current?.state === "recording") {
    stopListening();
  }
}, 12000);
```

**Etki:** Sonsuz kayıtları önler, gereksiz işleme süresini engeller.

---

## 4. 🔌 WebSocket Binary Transport

### 4.1 Binary Ses Chunk'ları (Base64 Yok)

**Dosya:** `frontend/src/hooks/useVoiceSession.js`, `frontend/src/pages/Menu.jsx`

```js
// Direkt binary ArrayBuffer gönderimi
const arrayBuffer = chunk instanceof Blob ? await chunk.arrayBuffer() : chunk;
wsRef.current.send(arrayBuffer);
```

|                   | Base64 JSON | Binary WebSocket               |
| ----------------- | ----------- | ------------------------------ |
| Boyut overhead    | +33%        | 0%                             |
| Encode/decode CPU | Var         | Yok                            |
| **Kazanç**        | —           | **%33 daha küçük, daha hızlı** |

### 4.2 ArrayBuffer Binary Tipi

```js
ws.binaryType = "arraybuffer"; // Blob yerine direkt ArrayBuffer
```

**Etki:** Blob → ArrayBuffer dönüşüm overhead'i ortadan kalkar.

### 4.3 Binary TTS Ses Streaming

**Dosya:** `backend/services/streaming_llm_bridge.py`

```python
async for audio_chunk in self.tts.speak_stream(text, start_time):
    if audio_chunk:
        await websocket_send_bytes(audio_chunk)  # PCM16 binary frame
```

**Etki:** TTS ses chunk'ları JSON sarmalı olmadan doğrudan binary olarak gönderilir.

---

## 5. ⚙️ Backend Async / Event Loop

### 5.1 uvloop Event Loop

**Dosya:** `start-optimized.sh`

```bash
uvicorn main:app --loop uvloop --ws websockets
```

**Etki:** Varsayılan asyncio'ya göre **2-4x daha hızlı** async I/O.

### 5.2 asyncio.to_thread — Blocking Çağrılar

**Dosya:** `backend/services/partial_stt.py`, `backend/services/stt.py`, `backend/services/llm.py`, `backend/services/tts_warmer.py`

```python
# fal_client sync çağrıları thread pool'da çalıştırılıyor
audio_url = await asyncio.to_thread(fal_client.upload_file, temp_file_path)
result = await asyncio.to_thread(fal_client.subscribe, self.model, ...)
stream = await asyncio.to_thread(sync_stream)
```

**Etki:** Blocking I/O çağrıları event loop'u bloklamaz → WebSocket her zaman responsive.

---

## 6. 🎙️ STT Optimizasyonları

### 6.1 Rate Limiting (500ms Minimum Aralık)

**Dosya:** `backend/services/partial_stt.py`

```python
self.min_request_interval = 0.5  # API'ye minimum 500ms aralıkla istek

time_since_last = process_start - self.last_request_time
if time_since_last < self.min_request_interval:
    wait_time = self.min_request_interval - time_since_last
    await asyncio.sleep(wait_time)
```

**Etki:** 429 rate limit hatalarını önler — retry latency'si oluşmaz.

### 6.2 Küçük Chunk Filtreleme (< 1KB Atla)

```python
if len(audio_data) < 1000:
    return {"text": "", "skipped": True}  # Sessizlik chunk'ını atla
```

**Etki:** Boş/gürültülü chunk'lar için API çağrısı yapılmaz.

### 6.3 Exponential Backoff ile Retry (3x)

```python
max_retries = 3
retry_delay = 2.0

for attempt in range(max_retries + 1):
    try:
        result = await asyncio.to_thread(fal_client.subscribe, ...)
        break
    except Exception as e:
        if "500" in error_str:
            wait_time = retry_delay * (2 ** attempt)  # 2s, 4s, 8s
            await asyncio.sleep(wait_time)
```

**Etki:** Geçici sunucu hatalarından kurtulur — pipeline'ı sıfırdan başlatmaya gerek kalmaz.

### 6.4 İşleme Kilidi (Seri STT)

```python
self.processing_lock = asyncio.Lock()

async with self.processing_lock:
    # Aynı session'dan eş zamanlı STT isteği yapılmaz
```

**Etki:** Yarış koşullarını ve tekrarlı API çağrılarını önler.

### 6.5 Base64 Audio (CDN Upload Atlanır)

**Dosya:** `backend/services/stt.py`

```python
# CDN upload yerine doğrudan base64 gönder
audio_b64 = base64.b64encode(audio_data).decode('utf-8')
result = await asyncio.to_thread(
    fal_client.subscribe, self.model,
    arguments={"audio": audio_b64, ...}
)
```

**Etki:** CDN upload round-trip'i (~200-500ms) atlanır.

### 6.6 Transkript Birleştirme (Dedup)

```python
def merge_transcripts(self, old: str, new: str) -> str:
    words_old = old.split()
    words_new = new.split()
    max_overlap = min(len(words_old), len(words_new), 5)
    for i in range(max_overlap, 0, -1):
        if words_old[-i:] == words_new[:i]:
            merged = old + " " + " ".join(words_new[i:])
            return merged.strip()
    return (old + " " + new).strip()
```

**Etki:** Örtüşen STT sonuçlarından tekrarlayan kelimeleri temizler.

---

## 7. 🧠 LLM Optimizasyonları

### 7.1 Ultra-Kompakt Sistem Prompt'u (~25 token)

**Dosya:** `backend/services/llm.py`

```python
self.system_prompt = """GarsonAI bot. Kısa yanıt (max 10 kelime).
JSON only: {"spoken_response":"...","intent":"add|info|hi","product_name":"...","quantity":1}"""
```

|              | Tipik prompt | Bizim prompt                                      |
| ------------ | ------------ | ------------------------------------------------- |
| Token sayısı | ~200-500     | ~25                                               |
| **Kazanç**   | —            | **10-20x daha az token → daha hızlı first token** |

### 7.2 Düşük max_tokens (100)

```python
"max_tokens": 100  # Sesli AI kısa yanıt veriyor
```

**Etki:** Üretim uzunluğunu sınırlar → yanıt süresi kısalır.

### 7.3 Menü Bağlamı Önbellekleme

```python
self._cached_menu = None

def cache_menu(self, menu_context: str):
    if self._cached_menu != menu_context:
        self._cached_menu = menu_context
```

**Etki:** Menü her istekte yeniden serileştirilmez.

### 7.4 Streaming LLM Token'ları

```python
async def generate_stream(self, user_message, menu_context, start_time):
    stream = fal_client.stream(self.model, arguments={...})
    for event in stream:
        yield {"type": "token", "content": new_content, "full_text": full_response}
```

**Etki:** Token'lar geldikçe client'a iletilir → paralel TTS tetiklemeyi mümkün kılar.

### 7.5 Erken LLM Tetikleme (Cümle Sınırı + Sessizlik)

**Dosya:** `backend/websocket/voice_session.py`

```python
def should_trigger_llm(self) -> bool:
    # Noktalama işareti ile biten cümle
    if self.partial_transcript.strip().endswith((".", "!", "?")):
        return True
    # 3+ kelime + 400ms sessizlik
    word_count = len(self.partial_transcript.split())
    if word_count >= 3:
        silence_duration = time.time() - self.last_chunk_time
        if silence_duration >= 0.4:  # SILENCE_THRESHOLD
            return True
```

**Etki:** Kullanıcı konuşmayı bitirmeden LLM üretimi başlar — büyük latency overlap'i.

---

## 8. 🔊 TTS Optimizasyonları

### 8.1 Streaming TTS (Gerçek Zamanlı Chunk'lar)

**Dosya:** `backend/services/tts.py`

```python
async def speak_stream(self, text, start_time):
    stream = fal_client.stream(
        self.model,
        arguments={
            "input": text,
            "voice": "zeynep",
            "speed": 1.15,       # %15 daha hızlı konuşma
        },
        path="/stream"           # ⚡ STREAMING MODU
    )
    for event in stream:
        if "audio" in event:
            pcm_bytes = base64.b64decode(event["audio"])
            yield pcm_bytes      # Anında WebSocket'e gönder
```

**Etki:** İlk ses chunk'ı ~200ms'de gelir vs. tüm sentezin bitmesini bekleme (~2-3s).

### 8.2 Hızlandırılmış Konuşma (1.15x)

```python
"speed": 1.15  # %15 daha hızlı
```

**Etki:** Toplam oynatma süresi %15 kısalır — kalite kaybı olmadan.

### 8.3 TTS Container Warmup (Keep-Alive)

**Dosya:** `backend/services/tts_warmer.py`, `backend/main.py`

```python
# Her 30 saniyede bir dummy istek ile container sıcak tutulur
self.interval = 30  # saniye

async def warmup_call(self):
    result = await asyncio.to_thread(
        fal_client.subscribe, self.model,
        arguments={"input": "test", "voice": "zeynep", ...}
    )

# Uygulama başladığında otomatik başlatılır
@asynccontextmanager
async def lifespan(app: FastAPI):
    start_tts_warmer(interval=30)
    yield
    stop_tts_warmer()
```

|                     | Cold Start   | Warm Container    |
| ------------------- | ------------ | ----------------- |
| İlk istek gecikmesi | ~2-3s kuyruk | ~0s               |
| **Kazanç**          | —            | **2-3s tasarruf** |

### 8.4 Paralel TTS Tetikleme (LLM Streaming Sırasında)

**Dosya:** `backend/services/streaming_llm_bridge.py`

```python
# İlk cümle tamamlanır tamamlanmaz TTS başlatılır
if first_sentence_complete and first_sentence:
    spoken_text = self._extract_spoken_response(first_sentence, full_response)
    if spoken_text:
        tts_task = asyncio.create_task(
            self._stream_tts_parallel(spoken_text, start_time, websocket_send_bytes)
        )
```

```
   LLM:  ████████████████████████████  (streaming)
   TTS:       ███████████████████       (ilk cümle sonrası başlar)
         ╔══════════════════════════════════════╗
         ║  TTS latency'si LLM ile örtüşür!    ║
         ╚══════════════════════════════════════╝
```

### 8.5 Cümle Sınırı Algılama

```python
def _detect_sentence_boundary(self, text):
    match = re.search(r'[.!?]\s*', text)
    if match:
        return True, text[:match.end()].strip()
    return False, ""
```

**Etki:** Tam LLM çıktısını beklemeden ilk cümle ile TTS başlar.

### 8.6 Fallback TTS

```python
async def _fallback_tts(self, structured_data, ...):
    if structured_data and "spoken_response" in structured_data:
        spoken_text = structured_data["spoken_response"]
        async for audio_chunk in self.tts.speak_stream(spoken_text, start_time):
            await websocket_send_bytes(audio_chunk)
```

**Etki:** Cümle sınırı algılanamasa bile TTS çıktısı garanti edilir.

---

## 9. 🎧 Ses Oynatma Optimizasyonları

### 9.1 Gapless Playback (Kesintisiz Oynatma)

**Dosya:** `frontend/src/utils/StreamingAudioPlayer.js`

```js
playNext() {
  const source = this.audioContext.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(this.audioContext.destination);

  // Hassas zamanlama ile kesintisiz oynatma
  const startTime = Math.max(this.audioContext.currentTime, this.nextStartTime);
  source.start(startTime);
  this.nextStartTime = startTime + audioBuffer.duration;

  source.onended = () => { this.playNext(); };
}
```

**Etki:** Web Audio API'nin `currentTime` tabanlı zamanlama ile chunk'lar arası sıfır boşluk.

### 9.2 Anında PCM16 Oynatma (Tamponsuz)

```js
async addPCMChunk(pcmBytes) {
  const audioBuffer = await this.pcmToAudioBuffer(pcmBytes);
  this.audioQueue.push(audioBuffer);
  if (!this.isPlaying) {
    this.isPlaying = true;
    this.nextStartTime = this.audioContext.currentTime;
    this.playNext();  // İlk chunk gelir gelmez başla
  }
}
```

**Etki:** Minimum tampon bekleme yok — ilk chunk geldiği anda oynatma başlar.

### 9.3 Doğrudan PCM16 → Float32 Dönüşümü

```js
async pcmToAudioBuffer(pcmBytes) {
  const samples = new Int16Array(pcmBytes);
  const floatSamples = new Float32Array(samples.length);
  for (let i = 0; i < samples.length; i++) {
    floatSamples[i] = samples[i] / 32768.0;  // Normalize [-1, 1]
  }
}
```

**Etki:** MP3/AAC decode overhead'i yok — hafif bellek içi dönüşüm.

### 9.4 Anında Barge-In Durdurma

```js
stopImmediately() {
  this.isPlaying = false;
  this.audioQueue = [];  // Kuyruğu temizle
  this.nextStartTime = this.audioContext.currentTime;
}
```

**Etki:** AI konuşurken kullanıcı sözünü kestiğinde anında durur, yeniden dinlemeye geçilebilir.

### 9.5 Kullanıcı Etkileşiminde AudioContext Ön-Başlatma

```js
// Butona tıklama sırasında başlatılır (autoplay policy)
await playerRef.current.initialize();
playerRef.current.reset();
```

**Etki:** Tarayıcı autoplay politikası gecikmesi önlenir.

---

## 10. 🔗 Connection Pooling & Keep-Alive

### 10.1 Singleton fal.ai Client + HTTP Bağlantı Havuzu

**Dosya:** `backend/core/fal_client_pool.py`

```python
@lru_cache(maxsize=1)
def get_fal_client():
    http_client = httpx.Client(
        timeout=30.0,
        limits=httpx.Limits(
            max_connections=10,
            max_keepalive_connections=5,
            keepalive_expiry=30.0
        )
    )

@lru_cache(maxsize=1)
def get_async_http_client():
    return httpx.AsyncClient(
        timeout=30.0,
        limits=httpx.Limits(
            max_connections=10,
            max_keepalive_connections=5,
            keepalive_expiry=30.0
        )
    )
```

**Etki:** Her istekte TCP/TLS el sıkışması yapılmaz — bağlantılar yeniden kullanılır.

### 10.2 Import Zamanında Ön-Başlatma

```python
# İlk client isteği maliyet ödemesin diye önceden başlat
_client = get_fal_client()
_async_client = get_async_http_client()
```

### 10.3 Ayarlar lru_cache ile Önbellek

```python
@lru_cache()
def get_settings():
    return Settings()
```

**Etki:** Çevre değişkenleri her istekte yeniden parse edilmez.

---

## 11. 🔄 Pipeline & WebSocket Optimizasyonları

### 11.1 Barge-In (AI Sözünü Kesme)

**Dosya:** `backend/services/streaming_llm_bridge.py`, `backend/routers/voice_routes.py`

```python
# Sunucu tarafı — aktif LLM/TTS task'larını iptal et
async def cancel_active_streams(self, session_id):
    task_key = f"{session_id}_tts"
    if task_key in self.active_tasks:
        task = self.active_tasks[task_key]
        if not task.done():
            task.cancel()

# WebSocket handler — interrupt mesajı
elif message.get("type") == "interrupt":
    await llm_bridge.cancel_active_streams(session.session_id)
    await session.cancel_active_streams()
    session.state = "LISTENING"
    session.partial_transcript = ""
    session.audio_buffer.clear()
```

**Etki:** Uçuştaki LLM/TTS görevleri anında iptal edilir → kaynaklar serbest bırakılır.

### 11.2 İstemci Tarafı Barge-In Algılama

```js
const BARGE_IN_THRESHOLD = 0.02; // RMS eşiği
const BARGE_IN_CHECK_INTERVAL_MS = 100; // 100ms'de bir kontrol
```

### 11.3 Heartbeat / Ping-Pong

```python
if message.get("type") == "ping":
    await websocket.send_json({"type": "pong"})
```

**Etki:** WebSocket bağlantısını canlı tutar, timeout kopuşlarını önler.

### 11.4 Singleton Servisler

```python
# StreamingLLMBridge
_bridge_instance: Optional[StreamingLLMBridge] = None

def get_llm_bridge() -> StreamingLLMBridge:
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = StreamingLLMBridge(...)
    return _bridge_instance
```

**Etki:** Servis nesneleri bir kez oluşturulur — tekrarlanan başlatma maliyeti yok.

---

## 12. 📋 Optimizasyon Özet Tablosu

| #   | Optimizasyon                   | Dosya                             | Kazanç                   |
| --- | ------------------------------ | --------------------------------- | ------------------------ |
| 1   | Mono kanal (stereo yerine)     | VoiceAI.jsx, Menu.jsx             | %50 daha az veri         |
| 2   | 16kHz örnekleme (48kHz yerine) | VoiceAI.jsx, Menu.jsx             | 3x daha az veri          |
| 3   | 16kbps Opus codec              | VoiceAI.jsx, Menu.jsx             | 8x daha küçük            |
| 4   | Tarayıcı ses işleme            | VoiceAI.jsx, Menu.jsx             | Sunucu yükü yok          |
| 5   | 500ms chunk streaming          | VoiceAI.jsx, Menu.jsx             | Gerçek zamanlı STT       |
| 6   | Incremental partial STT        | voice_routes.py, voice_session.py | Konuşurken işleme        |
| 7   | Buffer overlap (500ms)         | voice_session.py                  | Doğru STT bağlamı        |
| 8   | 800ms VAD eşiği                | VoiceActivityDetector.js          | 700ms daha hızlı stop    |
| 9   | 100ms VAD yoklama              | VoiceAI.jsx, Menu.jsx             | Anlık algılama           |
| 10  | Binary WebSocket               | useVoiceSession.js, Menu.jsx      | %33 daha küçük           |
| 11  | uvloop event loop              | start-optimized.sh                | 2-4x daha hızlı async    |
| 12  | asyncio.to_thread              | partial_stt.py, stt.py, llm.py    | Non-blocking I/O         |
| 13  | STT rate limiting (500ms)      | partial_stt.py                    | 429 hata önleme          |
| 14  | Chunk filtreleme (<1KB)        | partial_stt.py                    | Gereksiz API çağrısı yok |
| 15  | Retry + exponential backoff    | partial_stt.py                    | Hata dayanıklılığı       |
| 16  | Base64 audio (CDN atla)        | stt.py                            | 200-500ms tasarruf       |
| 17  | Transkript dedup               | partial_stt.py                    | Temiz transkript         |
| 18  | Kompakt prompt (~25 token)     | llm.py                            | Hızlı first token        |
| 19  | max_tokens: 100                | llm.py                            | Kısa yanıt süresi        |
| 20  | Menü önbellekleme              | llm.py                            | Tekrar serileştirme yok  |
| 21  | Streaming LLM token'ları       | llm.py                            | Paralel TTS mümkün       |
| 22  | Erken LLM tetikleme            | voice_session.py                  | Konuşma bitmeden LLM     |
| 23  | Streaming TTS                  | tts.py                            | ~200ms ilk ses           |
| 24  | 1.15x konuşma hızı             | tts.py                            | %15 kısa oynatma         |
| 25  | Container warmup (30s)         | tts_warmer.py, main.py            | 2-3s cold start yok      |
| 26  | Paralel TTS (LLM sırasında)    | streaming_llm_bridge.py           | TTS latency örtüşür      |
| 27  | Cümle sınırı algılama          | streaming_llm_bridge.py           | Erken TTS başlatma       |
| 28  | Gapless oynatma                | StreamingAudioPlayer.js           | Kesintisiz ses           |
| 29  | Tamponsuz oynatma              | StreamingAudioPlayer.js           | Anında ilk ses           |
| 30  | PCM16 → Float32 direkt         | StreamingAudioPlayer.js           | Decode overhead yok      |
| 31  | Anında barge-in stop           | StreamingAudioPlayer.js           | Anlık kesme              |
| 32  | HTTP bağlantı havuzu           | fal_client_pool.py                | TCP/TLS tekrarı yok      |
| 33  | Ön-başlatma (import)           | fal_client_pool.py                | İlk istek hızlı          |
| 34  | Ayarlar önbelleği              | config.py                         | Parse tekrarı yok        |
| 35  | Barge-in iptal                 | streaming_llm_bridge.py           | Kaynak serbest bırakma   |

---

## 13. ⏱️ Zamanlama Örneği (İdeal Durum)

```
[00:00.000] 🎤 Kullanıcı "Konuşmaya Başla"ya basıyor
[00:00.050] 🎙️ MediaRecorder başlıyor (Mono, 16kHz, Opus 16kbps)
[00:00.500] 📤 İlk 500ms chunk gönderildi → STT işleme başladı
[00:01.200] 📝 İlk partial transkript: "İki" (canlı görüntü)
[00:01.500] 📤 İkinci 500ms chunk gönderildi
[00:02.100] 📝 İkinci partial: "İki pizza" (güncellendi)
[00:02.500] 📤 Üçüncü 500ms chunk gönderildi
[00:03.000] 📝 Üçüncü partial: "İki pizza lütfen" (güncellendi)
[00:03.300] 🛑 Kullanıcı susuyor
[00:04.100] ⏹️ VAD eşiği (800ms) → Otomatik kayıt durdurma
[00:04.150] ✅ Final transkript: "İki pizza lütfen"
[00:04.200] 🧠 LLM başlıyor (Gemini 2.5 Flash)
[00:04.400] ⚡ LLM ilk token (200ms)
[00:04.450] 📝 İlk cümle tamamlandı → Paralel TTS başlıyor
[00:04.650] 🎵 TTS ilk chunk (200ms) ⚡
[00:04.670] 🔊 Kullanıcı sesi duyuyor! 🎧

💡 ALGILANAN LATENCY: 0.57 saniye (kayıt durmasından ilk sese kadar)
```
