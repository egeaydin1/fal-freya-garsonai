import { useState, useEffect, useRef, useCallback } from "react";
import { useParams } from "react-router-dom";
import MenuProductCard from "../components/MenuProductCard";
import Cart from "../components/Cart";
import RecommendationPopup from "../components/RecommendationCard";
import { VoiceActivityDetector } from "../utils/VoiceActivityDetector";
import { AudioCompressor } from "../utils/AudioCompressor";
import { StreamingAudioPlayer } from "../utils/StreamingAudioPlayer";

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
  const [recommendation, setRecommendation] = useState(null);

  // ── Voice state ──
  // idle → listening → processing → playing → idle
  const [voiceState, setVoiceState] = useState("idle");
  const [greeting, setGreeting] = useState("");
  const [transcript, setTranscript] = useState("");
  const [aiResponse, setAiResponse] = useState("");
  const isPlayingRef = useRef(false);

  // ── Refs ──
  const wsRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const vadRef = useRef(null);
  const compressorRef = useRef(new AudioCompressor());
  const playerRef = useRef(null);
  const checkIntervalRef = useRef(null);

  // Initialize player with playback-complete callback
  useEffect(() => {
    const player = new StreamingAudioPlayer({
      onPlaybackComplete: () => {
        console.log("🔇 Playback complete → ready to listen");
        isPlayingRef.current = false;
        setVoiceState("idle");
        // Notify backend that playback is done
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: "playback_complete" }));
        }
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

    const ws = new WebSocket(`ws://localhost:8000/ws/voice/${qrToken}`);
    wsRef.current = ws;

    ws.onmessage = async (event) => {
      // Binary → audio chunk
      if (event.data instanceof Blob) {
        const buf = await event.data.arrayBuffer();
        await playerRef.current.addPCMChunk(buf);
        return;
      }

      const data = JSON.parse(event.data);

      switch (data.type) {
        case "greeting":
          setGreeting(data.text);
          break;

        case "status":
          if (data.message === "transcribing") setVoiceState("processing");
          else if (data.message === "thinking") setVoiceState("processing");
          else if (data.message === "processing") setVoiceState("processing");
          break;

        case "transcript":
          setTranscript(data.text);
          break;

        case "ai_token":
          setAiResponse((prev) => prev + (data.token || ""));
          break;

        case "recommendation":
          setRecommendation(data.product);
          break;

        case "tts_start":
          isPlayingRef.current = true;
          setVoiceState("playing");
          break;

        case "tts_complete":
          // Mark finalized so player fires onPlaybackComplete when queue drains
          if (playerRef.current) playerRef.current.finalize();
          break;

        case "error":
          console.error("Voice error:", data.message);
          isPlayingRef.current = false;
          setVoiceState("idle");
          break;
      }
    };

    ws.onerror = () => setVoiceState("idle");
    ws.onclose = () => { isPlayingRef.current = false; setVoiceState("idle"); };
  }, [qrToken]);

  // ── Voice recording ──
  const startListening = async () => {
    // DON'T listen while playing audio
    if (isPlayingRef.current || voiceState === "playing") {
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
          setTimeout(() => { clearInterval(check); resolve(); }, 2000);
        });
      }

      // Pre-initialize AudioContext on user gesture (required for TTS playback)
      await playerRef.current.initialize();
      // Reset player for new session
      playerRef.current.reset();

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const vad = new VoiceActivityDetector(stream);
      vadRef.current = vad;
      await vad.initialize();

      const recorder = new MediaRecorder(stream, {
        mimeType: "audio/webm;codecs=opus",
      });
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = async (e) => {
        if (e.data.size > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
          const compressed = await compressorRef.current.compress(e.data);
          wsRef.current.send(compressed);
          setVoiceState("processing");
          setAiResponse("");
          cleanupRecording();
        }
      };

      // VAD polling: wait for speech start, then detect silence
      let speechDetected = false;
      checkIntervalRef.current = setInterval(() => {
        const speaking = vad.isSpeaking();
        if (speaking && !speechDetected) {
          speechDetected = true;
          console.log("🎤 Speech detected");
        } else if (!speaking && speechDetected) {
          // Speech ended → stop recording
          console.log("🔇 Speech ended → sending audio");
          clearInterval(checkIntervalRef.current);
          if (recorder.state === "recording") recorder.stop();
        }
      }, 100); // Check every 100ms

      recorder.start();
      setVoiceState("listening");
      setTranscript("");
      setAiResponse("");

      // Safety timeout
      setTimeout(() => {
        if (recorder.state === "recording") {
          clearInterval(checkIntervalRef.current);
          recorder.stop();
        }
      }, 12000);
    } catch (err) {
      console.error("Mic error:", err);
      setVoiceState("idle");
    }
  };

  const cleanupRecording = () => {
    if (checkIntervalRef.current) clearInterval(checkIntervalRef.current);
    if (mediaRecorderRef.current?.state === "recording") mediaRecorderRef.current.stop();
    if (streamRef.current) streamRef.current.getTracks().forEach((t) => t.stop());
    if (vadRef.current) vadRef.current.cleanup();
  };

  const cleanupVoice = () => {
    cleanupRecording();
  };

  // ── Cart operations ──
  const addToCart = (product) => {
    setCart((prev) => {
      const existing = prev.find((i) => i.product_id === product.id);
      if (existing) {
        return prev.map((i) =>
          i.product_id === product.id ? { ...i, quantity: i.quantity + 1 } : i
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
          i.product_id === productId ? { ...i, quantity: i.quantity - 1 } : i
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
        `http://localhost:8000/api/menu/${qrToken}/checkout`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ items }),
        }
      );
      if (res.ok) {
        setCart([]);
        setShowCart(false);
      }
    } catch (err) {
      console.error("Checkout error:", err);
    }
  };

  const fetchMenu = async () => {
    try {
      const res = await fetch(`http://localhost:8000/api/menu/${qrToken}`);
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
            {transcript && (
              <div className="bg-base-200 rounded-xl p-3 text-sm animate-fade-in-up">
                <span className="opacity-50 text-xs">Siz:</span>
                <p className="font-medium">{transcript}</p>
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
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z" />
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
              onClick={startListening}
              disabled={voiceState === "listening" || voiceState === "processing" || voiceState === "playing"}
            >
              {voiceState === "processing" ? (
                <span className="loading loading-spinner loading-md" />
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                </svg>
              )}
            </button>

            {/* Voice Panel Toggle */}
            <button
              className={`btn btn-ghost flex-1 rounded-xl gap-2 ${showVoice ? "btn-active" : ""}`}
              onClick={() => setShowVoice(!showVoice)}
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
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
      {recommendation && (
        <RecommendationPopup
          product={recommendation}
          onAdd={addToCart}
          onClose={() => setRecommendation(null)}
        />
      )}
    </div>
  );
}
