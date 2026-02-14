import { useState, useEffect, useRef, useCallback } from "react";
import { useParams } from "react-router-dom";
import MenuProductCard from "../components/MenuProductCard";
import Cart from "../components/Cart";
import RecommendationPopup from "../components/RecommendationCard";
import { VoiceActivityDetector } from "../utils/VoiceActivityDetector";
import { StreamingAudioPlayer } from "../utils/StreamingAudioPlayer";
import { config } from "../config";

// ── Suggestion chips for the voice panel ──
const SUGGESTIONS = [
  { text: "Ne önerirsin?", icon: "💡" },
  { text: "En popüler ne?", icon: "🔥" },
  { text: "Vegan seçenekler", icon: "🌱" },
  { text: "Tatlı istiyorum", icon: "🍰" },
  { text: "İçecek öner", icon: "🥤" },
  { text: "Hesabı istiyorum", icon: "💳" },
];

export default function Menu() {
  const { qrToken } = useParams();

  // ── Data state ──
  const [products, setProducts] = useState([]);
  const [cart, setCart] = useState([]);

  // ── UI state ──
  const [showCart, setShowCart] = useState(false);
  const [showVoice, setShowVoice] = useState(false);
  const [pendingRecommendation, setPendingRecommendation] = useState(null);
  const [showRecommendation, setShowRecommendation] = useState(false);

  // ── Voice state ──
  // idle → listening → processing → playing → idle
  const [voiceState, setVoiceState] = useState("idle");
  const [greeting, setGreeting] = useState("");
  const [transcript, setTranscript] = useState("");
  const [partialTranscript, setPartialTranscript] = useState("");
  const [aiResponse, setAiResponse] = useState("");
  const isPlayingRef = useRef(false);

  // ── Refs ──
  const wsRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const vadRef = useRef(null);
  const vadIntervalRef = useRef(null);
  const playerRef = useRef(null);
  const startListeningRef = useRef(null);
  const showVoiceRef = useRef(showVoice);
  const voiceStateRef = useRef(voiceState);
  const audioChunksRef = useRef([]);
  const pendingFinalizeTimeoutRef = useRef(null);
  const ttsCompleteReceivedRef = useRef(false);

  useEffect(() => {
    showVoiceRef.current = showVoice;
  }, [showVoice]);

  useEffect(() => {
    voiceStateRef.current = voiceState;
  }, [voiceState]);

  // ── Cleanup stream when voice panel closes ──
  useEffect(() => {
    if (!showVoice) {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
      // Also stop player if playing
      if (playerRef.current) {
         playerRef.current.stop();
      }
      if (voiceState !== "idle") {
        setVoiceState("idle");
      }
    }
  }, [showVoice]);

  // Initialize player with playback-complete callback (speak loop: auto-restart listening)
  useEffect(() => {
    const player = new StreamingAudioPlayer({
      onPlaybackComplete: () => {
        console.log("🔇 Playback complete → ready to listen (speak loop)");
        isPlayingRef.current = false;
        setVoiceState("idle");
        
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: "playback_complete" }));
        }

        // Speak loop: automatically start listening again when voice panel is open
        // Increased delay to 500ms to prevent echo (mic picking up last TTS sounds)
        setTimeout(() => {
          if (
            startListeningRef.current &&
            wsRef.current?.readyState === WebSocket.OPEN &&
            showVoiceRef.current
          ) {
            console.log("🔄 Auto-restarting listener...");
            startListeningRef.current();
          }
        }, 500);
      },
    });
    playerRef.current = player;
  }, []);

  // ── Fetch menu on mount ──
  useEffect(() => {
    fetchMenu();
  }, [qrToken]);

  // ── Cleanup on unmount ──
  useEffect(() => {
    return () => {
      cleanupVoice();
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  // ── Auto-connect WebSocket for greeting ──
  useEffect(() => {
    connectWebSocket();
  }, [qrToken]);

  // ── WebSocket connection ──
  const connectWebSocket = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(`${config.WS_URL}/ws/voice/${qrToken}`);
    wsRef.current = ws;

    const scheduleFinalizeAfterChunks = () => {
      if (pendingFinalizeTimeoutRef.current) clearTimeout(pendingFinalizeTimeoutRef.current);
      pendingFinalizeTimeoutRef.current = setTimeout(() => {
        pendingFinalizeTimeoutRef.current = null;
        ttsCompleteReceivedRef.current = false;
        if (playerRef.current) {
          playerRef.current.finalize();
          console.log("🔇 Finalize after last chunk (conversation done)");
        }
      }, 600); // 600ms after last chunk = no more in flight
    };

    ws.onmessage = async (event) => {
      // Binary → audio chunk
      if (event.data instanceof Blob) {
        console.log("[Voice API] audio chunk", event.data.size, "bytes");
        if (ttsCompleteReceivedRef.current) scheduleFinalizeAfterChunks();
        const buf = await event.data.arrayBuffer();
        await playerRef.current.addPCMChunk(buf);
        return;
      }

      const data = JSON.parse(event.data);
      // Konuşma/yanıt akışında gelen tüm API yanıtlarını yazdır
      console.log("[Voice API response]", data.type, data);

      switch (data.type) {
        case "greeting":
          setGreeting(data.text);
          break;

        case "status":
          if (data.message === "receiving") setVoiceState("listening");
          else if (data.message === "transcribing") setVoiceState("processing");
          else if (data.message === "thinking") setVoiceState("processing");
          else if (data.message === "processing") setVoiceState("processing");
          break;

        case "partial_transcript":
          // Incremental STT while user speaks
          setPartialTranscript(data.text);
          break;

        case "transcript":
          setTranscript(data.text);
          setPartialTranscript(""); // Clear partial
          break;

        case "ai_token":
          // Try to extract spoken_response from streaming JSON
          try {
            const fullText = data.full_text;
            if (fullText.includes("{") && fullText.includes("}")) {
              const jsonStart = fullText.indexOf("{");
              const jsonEnd = fullText.lastIndexOf("}") + 1;
              const jsonStr = fullText.substring(jsonStart, jsonEnd);
              const parsed = JSON.parse(jsonStr);
              setAiResponse(parsed.spoken_response || fullText);
            } else {
              setAiResponse(fullText);
            }
          } catch (e) {
            setAiResponse(data.full_text);
          }
          break;

        case "ai_complete":
          console.log("🎯 AI complete:", data.data);
          break;

        case "recommendation":
          setPendingRecommendation(data.product);
          break;

        case "tts_start":
          if (pendingFinalizeTimeoutRef.current) {
            clearTimeout(pendingFinalizeTimeoutRef.current);
            pendingFinalizeTimeoutRef.current = null;
          }
          ttsCompleteReceivedRef.current = false;
          isPlayingRef.current = true;
          setVoiceState("playing");
          console.log("🔊 AI speech starting (tts_start)");
          if (pendingRecommendation) setShowRecommendation(true);
          break;

        case "tts_complete":
          // Don't finalize yet: last chunks may still be in flight. Wait 600ms after last chunk.
          ttsCompleteReceivedRef.current = true;
          scheduleFinalizeAfterChunks();
          break;

        case "interrupt_ack":
          // Server acknowledged barge-in
          console.log("🛑 Barge-in acknowledged");
          isPlayingRef.current = false;
          setVoiceState("idle");
          break;

        case "error":
          console.error("Voice error:", data.message);
          isPlayingRef.current = false;
          setVoiceState("idle");
          break;

        case "pong":
          break;
      }
    };

    ws.onerror = () => setVoiceState("idle");
    ws.onclose = () => {
      isPlayingRef.current = false;
      setVoiceState("idle");
    };
  }, [qrToken]);

  // ── Voice recording (ref for speak-loop callback) ──
  const startListening = async () => {
    // DON'T listen while playing audio
    if (isPlayingRef.current || voiceStateRef.current === "playing") {
      console.log("⚠️ Cannot listen while playing");
      return;
    }
    try {
      // Ensure WebSocket is connected
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        connectWebSocket();
        // Wait for connection
        await new Promise((resolve) => {
          const check = setInterval(() => {
            if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
              clearInterval(check);
              resolve();
            }
          }, 50);
          setTimeout(() => {
            clearInterval(check);
            resolve();
          }, 2000);
        });
      }

      // Pre-initialize AudioContext on user gesture (required for TTS playback)
      await playerRef.current.initialize();
      // Reset player for new session
      playerRef.current.reset();

      // Get audio stream (reuse if available to support continuous loop on mobile)
      let stream = streamRef.current;
      if (!stream || !stream.getAudioTracks().some((t) => t.readyState === "live")) {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1, // Mono
            sampleRate: 16000, // 16kHz (STT native)
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });
        streamRef.current = stream;
      }

      // Initialize VAD with 800ms aggressive threshold
      const vad = new VoiceActivityDetector({
        silenceThreshold: 0.01,
        silenceDuration: 1200,
      });
      vad.initializeAnalyzer(stream);
      vad.reset();
      vadRef.current = vad;

      // Accumulate audio; send to API only when user stops speaking
      audioChunksRef.current = [];

      // Setup MediaRecorder with 1s chunks (no streaming to API until stop)
      let recorder;
      const preferredMime = "audio/webm;codecs=opus";
      if (MediaRecorder.isTypeSupported(preferredMime)) {
        recorder = new MediaRecorder(stream, {
          mimeType: preferredMime,
          audioBitsPerSecond: 16000, // 16kbps low bitrate
        });
      } else {
        recorder = new MediaRecorder(stream, {
          mimeType: "audio/webm",
          audioBitsPerSecond: 16000,
        });
      }
      mediaRecorderRef.current = recorder;

      // Collect chunks locally; do not send to API until recording stops
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      // On stop: send full audio once, then audio_end (API request only after speech ends)
      recorder.onstop = async () => {
        const chunks = audioChunksRef.current;
        if (chunks.length > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
          const blob = new Blob(chunks, { type: "audio/webm" });
          const buf = await blob.arrayBuffer();
          wsRef.current.send(buf);
          console.log("📤 Sent full audio", buf.byteLength, "bytes");
        }
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: "audio_end" }));
          console.log("📤 Sent audio_end");
        }
      };

      // VAD polling: detect silence to auto-stop
      vadIntervalRef.current = setInterval(() => {
        if (vadRef.current) {
          const vadStatus = vadRef.current.analyzeAudioLevel();
          if (vadStatus === "SILENCE_DETECTED") {
            stopListening();
          }
        }
      }, 80);

      // 1s chunks; API is only called after user stops (in onstop)
      recorder.start(1000);
      setVoiceState("listening");
      setTranscript("");
      setPartialTranscript("");
      setAiResponse("");

      // Safety timeout (12s max recording)
      setTimeout(() => {
        if (mediaRecorderRef.current?.state === "recording") {
          console.log("⏱️ Safety timeout: stopping recording");
          stopListening();
        }
      }, 12000);
    } catch (err) {
      console.error("Mic error:", err);
      setVoiceState("idle");
    }
  };
  startListeningRef.current = startListening;

  // ── Stop recording and send audio_end signal ──
  const stopListening = () => {
    // Clear VAD interval
    if (vadIntervalRef.current) {
      clearInterval(vadIntervalRef.current);
      vadIntervalRef.current = null;
    }

    // Stop MediaRecorder
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop();
    }

    // Do NOT stop media stream tracks here to allow quick restart (speak loop)
    // Stream will be stopped when component unmounts or voice panel closes
    /*
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    */

    // Cleanup VAD
    if (vadRef.current) {
      vadRef.current.cleanup();
      vadRef.current = null;
    }

    // audio_end is sent from recorder.onstop after full audio is uploaded
    setVoiceState("processing");
  };
  // Update ref on every render to capture latest closure
  startListeningRef.current = startListening;

  // ━━━ Interrupt AI (barge-in) ━━━
  const handleInterrupt = () => {
    // Stop player immediately
    if (playerRef.current) {
      playerRef.current.stopImmediately();
    }

    // Send interrupt signal to backend
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "interrupt" }));
      console.log("📤 Sent interrupt");
    }

    isPlayingRef.current = false;
    setVoiceState("idle");
    setAiResponse("");
  };

  const cleanupVoice = () => {
    if (vadIntervalRef.current) clearInterval(vadIntervalRef.current);
    if (mediaRecorderRef.current?.state === "recording")
      mediaRecorderRef.current.stop();
    if (streamRef.current)
      streamRef.current.getTracks().forEach((t) => t.stop());
    if (vadRef.current) vadRef.current.cleanup();
  };

  // ── Cart operations ──
  const addToCart = (product) => {
    setCart((prev) => {
      const existing = prev.find((i) => i.product_id === product.id);
      if (existing) {
        return prev.map((i) =>
          i.product_id === product.id ? { ...i, quantity: i.quantity + 1 } : i,
        );
      }
      return [...prev, { product_id: product.id, quantity: 1, product }];
    });
  };

  const removeFromCart = (productId) => {
    setCart((prev) => {
      const existing = prev.find((i) => i.product_id === productId);
      if (existing && existing.quantity > 1) {
        return prev.map((i) =>
          i.product_id === productId ? { ...i, quantity: i.quantity - 1 } : i,
        );
      }
      return prev.filter((i) => i.product_id !== productId);
    });
  };

  const checkout = async () => {
    const items = cart.map((i) => ({
      product_id: i.product_id,
      quantity: i.quantity,
    }));

    try {
      const res = await fetch(
        `${config.API_BASE}/api/menu/${qrToken}/checkout`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ items }),
        },
      );
      if (res.ok) {
        const data = await res.json();
        alert(data.message || "Siparişiniz alındı!");
        setCart([]);
        setShowCart(false);
      } else {
        alert("Sipariş oluşturulamadı!");
      }
    } catch (err) {
      console.error("Checkout error:", err);
    }
  };

  const requestCheck = async () => {
    try {
      const res = await fetch(
        `${config.API_BASE}/api/menu/${qrToken}/request-check`,
        { method: "POST" },
      );
      if (res.ok) {
        const data = await res.json();
        alert(data.message || "Hesap isteğiniz iletildi!");
      } else {
        alert("Hesap isteği gönderilemedi!");
      }
    } catch (err) {
      console.error("Request check error:", err);
    }
  };

  const fetchMenu = async () => {
    try {
      const res = await fetch(`${config.API_BASE}/api/menu/${qrToken}`);
      if (res.ok) setProducts(await res.json());
    } catch (err) {
      console.error("Menu fetch error:", err);
    }
  };

  // ── Computed ──
  const total = cart.reduce((s, i) => s + i.product.price * i.quantity, 0);
  const cartCount = cart.reduce((s, i) => s + i.quantity, 0);
  const getCartQuantity = (productId) =>
    cart.find((i) => i.product_id === productId)?.quantity || 0;

  return (
    <div className="min-h-screen bg-gradient-to-b from-base-200 to-base-300 pb-28">
      {/* ━━━ Header ━━━ */}
      <header className="bg-base-100/90 backdrop-blur-lg border-b border-base-200 sticky top-0 z-50">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
          <h1 className="text-xl font-bold tracking-tight">Menü</h1>

          {/* Greeting text */}
          {greeting && (
            <p className="text-xs opacity-60 hidden sm:block max-w-[200px] truncate">
              {greeting}
            </p>
          )}
        </div>
      </header>

      {/* ━━━ Greeting Banner ━━━ */}
      {greeting && (
        <div className="max-w-2xl mx-auto px-4 pt-4 animate-fade-in-up">
          <div className="glass-card rounded-2xl p-4 flex items-center gap-3">
            <span className="text-3xl">👋</span>
            <p className="text-sm leading-relaxed opacity-80">{greeting}</p>
          </div>
        </div>
      )}

      {/* ━━━ Voice Panel (expandable) ━━━ */}
      {showVoice && (
        <div className="max-w-2xl mx-auto px-4 pt-4 animate-slide-down">
          <div className="bg-base-100 rounded-2xl shadow-lg p-5 space-y-4">
            {/* Voice Status */}
            <div className="flex flex-col items-center gap-3">
              {voiceState === "listening" && (
                <div className="flex items-center gap-2 text-error animate-breathe">
                  <div className="w-3 h-3 rounded-full bg-error animate-pulse" />
                  <span className="font-medium">Dinliyorum...</span>
                </div>
              )}
              {voiceState === "processing" && (
                <div className="flex items-center gap-2 text-warning">
                  <span className="loading loading-dots loading-sm" />
                  <span className="font-medium">Düşünüyorum...</span>
                </div>
              )}
              {voiceState === "playing" && (
                <div className="flex items-center gap-2 text-info">
                  <span className="loading loading-bars loading-sm" />
                  <span className="font-medium">Konuşuyorum...</span>
                </div>
              )}
              {voiceState === "idle" && (
                <p className="text-sm opacity-50">Mikrofona basıp konuşun</p>
              )}
            </div>

            {/* Transcript */}
            {(partialTranscript || transcript) && (
              <div className="bg-base-200 rounded-xl p-3 text-sm animate-fade-in-up">
                <span className="opacity-50 text-xs">Siz:</span>
                <p className="font-medium">
                  {transcript || partialTranscript + "..."}
                </p>
              </div>
            )}

            {/* AI Response */}
            {aiResponse && (
              <div className="bg-primary/10 rounded-xl p-3 text-sm animate-fade-in-up">
                <span className="opacity-50 text-xs">AI:</span>
                <p>{aiResponse}</p>
              </div>
            )}

            {/* Suggestion Chips */}
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s.text}
                  className="btn btn-sm btn-outline rounded-full gap-1 animate-fade-in-scale"
                  onClick={startListening}
                >
                  {s.icon} {s.text}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ━━━ Products Grid ━━━ */}
      <div className="max-w-2xl mx-auto px-4 pt-5">
        <div className="grid grid-cols-2 gap-3 stagger-children">
          {products.map((product) => (
            <MenuProductCard
              key={product.id}
              product={product}
              onAdd={addToCart}
              cartQuantity={getCartQuantity(product.id)}
            />
          ))}
        </div>
        {products.length === 0 && (
          <div className="text-center py-16 opacity-40">
            <span className="text-5xl block mb-3">📋</span>
            <p>Menü yükleniyor...</p>
          </div>
        )}
      </div>

      {/* ━━━ Bottom Navigation Bar ━━━ */}
      <nav className="fixed bottom-0 left-0 right-0 z-50">
        <div className="max-w-2xl mx-auto px-4 pb-4 pt-2">
          <div className="bg-base-100/95 backdrop-blur-xl rounded-2xl shadow-2xl border border-base-200 px-3 py-2 flex items-center justify-between gap-2">
            {/* Cart Button */}
            <button
              className="btn btn-ghost flex-1 rounded-xl gap-2 relative"
              onClick={() => setShowCart(true)}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z"
                />
              </svg>
              <span className="text-sm font-medium">Sepet</span>
              {cartCount > 0 && (
                <span className="absolute -top-1 -right-1 badge badge-primary badge-sm animate-pop-bounce">
                  {cartCount}
                </span>
              )}
            </button>

            {/* Mic Button (center, prominent) */}
            <button
              className={`btn btn-circle btn-lg shadow-lg transition-all duration-300 ${
                voiceState === "listening"
                  ? "btn-error animate-mic-pulse"
                  : voiceState === "processing"
                    ? "btn-warning"
                    : voiceState === "playing"
                      ? "btn-info"
                      : "btn-primary animate-pulse-glow"
              }`}
              onClick={
                voiceState === "listening"
                  ? stopListening
                  : voiceState === "playing"
                    ? handleInterrupt
                    : startListening
              }
              disabled={voiceState === "processing"}
            >
              {voiceState === "processing" ? (
                <span className="loading loading-spinner loading-md" />
              ) : voiceState === "listening" ? (
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-7 w-7"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"
                  />
                </svg>
              ) : voiceState === "playing" ? (
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-7 w-7"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              ) : (
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-7 w-7"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
                  />
                </svg>
              )}
            </button>

            {/* Voice Panel Toggle */}
            <button
              className={`btn btn-ghost flex-1 rounded-xl gap-2 ${showVoice ? "btn-active" : ""}`}
              onClick={() => setShowVoice(!showVoice)}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                />
              </svg>
              <span className="text-sm font-medium">Asistan</span>
            </button>
          </div>
        </div>
      </nav>

      {/* ━━━ Cart Sheet ━━━ */}
      {showCart && (
        <Cart
          cart={cart}
          total={total}
          onAdd={addToCart}
          onRemove={removeFromCart}
          onCheckout={checkout}
          onClose={() => setShowCart(false)}
        />
      )}

      {/* ━━━ Recommendation Popup ━━━ */}
      {showRecommendation && pendingRecommendation && (
        <RecommendationPopup
          product={pendingRecommendation}
          onAdd={addToCart}
          onClose={() => {
            setShowRecommendation(false);
            setPendingRecommendation(null);
          }}
        />
      )}
    </div>
  );
}
