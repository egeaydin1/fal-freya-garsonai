import { VoiceActivityDetector } from "../utils/VoiceActivityDetector";
import { config } from "../config";

/**
 * Voice session modes for full-duplex streaming
 */
export const VoiceMode = {
  IDLE: "idle", // Not active
  LISTENING: "listening", // Recording user speech
  THINKING: "thinking", // Processing STT/LLM
  SPEAKING: "speaking", // AI is speaking (TTS playback)
};

/**
 * useVoiceSession Hook - Full-duplex voice state management
 * Handles modes, barge-in detection, partial transcripts, and WebSocket communication
 */
export default function useVoiceSession() {
  const [mode, setMode] = useState(VoiceMode.IDLE);
  const [partialTranscript, setPartialTranscript] = useState("");
  const [finalTranscript, setFinalTranscript] = useState("");
  const [aiResponse, setAiResponse] = useState("");
  const [error, setError] = useState(null);

  // Refs for audio detection and WebSocket
  const vadRef = useRef(null);
  const wsRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const bargeInCheckIntervalRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);

  // Barge-in threshold (RMS amplitude when AI is speaking)
  const BARGE_IN_THRESHOLD = 0.02; // Lower than VAD threshold (0.01) for sensitivity
  const BARGE_IN_CHECK_INTERVAL_MS = 100; // Check every 100ms

  /**
   * Stop barge-in detection
   */
  const stopBargeInDetection = useCallback(() => {
    if (bargeInCheckIntervalRef.current) {
      clearInterval(bargeInCheckIntervalRef.current);
      bargeInCheckIntervalRef.current = null;
    }
  }, []);

  /**
   * Handle barge-in (user interrupts AI)
   */
  const handleBargeIn = useCallback(() => {
    stopBargeInDetection();

    // Send interrupt message to server
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "interrupt" }));
      console.log("📤 Sent interrupt");
    }

    // Return to IDLE, parent component will restart listening if needed
    setMode(VoiceMode.IDLE);
    setAiResponse("");
  }, [stopBargeInDetection]);

  /**
   * Start barge-in detection (monitor mic while AI speaks)
   */
  const startBargeInDetection = useCallback(() => {
    if (!analyserRef.current) return;

    const analyser = analyserRef.current;
    const bufferLength = analyser.fftSize;
    const dataArray = new Uint8Array(bufferLength);

    bargeInCheckIntervalRef.current = setInterval(() => {
      analyser.getByteTimeDomainData(dataArray);

      // Calculate RMS amplitude
      let sum = 0;
      for (let i = 0; i < bufferLength; i++) {
        const normalized = (dataArray[i] - 128) / 128;
        sum += normalized * normalized;
      }
      const rms = Math.sqrt(sum / bufferLength);

      // If user speaks while AI is talking, send interrupt
      if (rms > BARGE_IN_THRESHOLD) {
        console.log(
          `🛑 BARGE-IN DETECTED! (RMS: ${rms.toFixed(4)} > ${BARGE_IN_THRESHOLD})`,
        );
        handleBargeIn();
      }
    }, BARGE_IN_CHECK_INTERVAL_MS);
  }, [handleBargeIn, BARGE_IN_THRESHOLD, BARGE_IN_CHECK_INTERVAL_MS]);

  /**
   * Handle WebSocket JSON messages
   */
  const handleWebSocketMessage = useCallback(
    (message) => {
      switch (message.type) {
        case "status":
          if (message.message === "receiving") {
            setMode(VoiceMode.LISTENING);
          } else if (message.message === "processing") {
            setMode(VoiceMode.THINKING);
          } else if (message.message === "thinking") {
            setMode(VoiceMode.THINKING);
          }
          break;

        case "partial_transcript":
          // Incremental STT while user speaks
          setPartialTranscript(message.text);
          break;

        case "transcript":
          // Final STT result
          setFinalTranscript(message.text);
          setPartialTranscript(""); // Clear partial
          break;

        case "ai_token":
          // LLM streaming tokens
          setAiResponse(message.full_text);
          setMode(VoiceMode.THINKING);
          break;

        case "ai_complete":
          // LLM finished
          console.log("🎯 LLM complete:", message.data);
          break;

        case "tts_start":
          // TTS audio playback starting
          setMode(VoiceMode.SPEAKING);
          // Barge-in disabled - user has manual control via Stop button
          // startBargeInDetection();
          break;

        case "tts_complete":
          // TTS finished - return to IDLE (not auto-listening)
          // CRITICAL: Stop MediaRecorder and close mic stream to prevent auto-restart
          if (
            mediaRecorderRef.current &&
            mediaRecorderRef.current.state !== "inactive"
          ) {
            mediaRecorderRef.current.stop();
            console.log("🛑 MediaRecorder stopped (tts_complete)");
          }
          if (streamRef.current) {
            streamRef.current.getTracks().forEach((track) => track.stop());
            streamRef.current = null;
            console.log("🎤 Microphone stream closed (tts_complete)");
          }
          if (vadRef.current) {
            if (vadRef.current.intervalId) {
              clearInterval(vadRef.current.intervalId);
            }
            vadRef.current.cleanup();
            vadRef.current = null;
          }
          setMode(VoiceMode.IDLE);
          stopBargeInDetection();
          setAiResponse("");
          setFinalTranscript(""); // Clear transcript for next turn
          break;

        case "interrupt_ack":
          // Server acknowledged barge-in - stay in IDLE for manual restart
          console.log("🛑 Barge-in acknowledged");
          // CRITICAL: Stop MediaRecorder and close mic stream to prevent auto-restart
          if (
            mediaRecorderRef.current &&
            mediaRecorderRef.current.state !== "inactive"
          ) {
            mediaRecorderRef.current.stop();
            console.log("🛑 MediaRecorder stopped (interrupt_ack)");
          }
          if (streamRef.current) {
            streamRef.current.getTracks().forEach((track) => track.stop());
            streamRef.current = null;
            console.log("🎤 Microphone stream closed (interrupt_ack)");
          }
          if (vadRef.current) {
            if (vadRef.current.intervalId) {
              clearInterval(vadRef.current.intervalId);
            }
            vadRef.current.cleanup();
            vadRef.current = null;
          }
          setMode(VoiceMode.IDLE);
          stopBargeInDetection();
          break;

        case "error":
          console.error("❌ Server error:", message.message);
          setError(message.message);
          setMode(VoiceMode.IDLE);
          break;

        case "pong":
          // Heartbeat response
          break;

        default:
          console.warn("Unknown message type:", message.type);
      }
    },
    [startBargeInDetection, stopBargeInDetection],
  );

  /**
   * Stop listening (send audio_end to server)
   */
  const stopListening = useCallback(() => {
    // Stop MediaRecorder first
    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state !== "inactive"
    ) {
      mediaRecorderRef.current.stop();
      console.log("🛑 MediaRecorder stopped");
    }

    // Stop media stream tracks
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (vadRef.current) {
      // Clear VAD polling interval
      if (vadRef.current.intervalId) {
        clearInterval(vadRef.current.intervalId);
      }
      vadRef.current.cleanup();
      vadRef.current = null;
    }

    // audio_end is sent by the component in MediaRecorder.onstop after sending full audio
    setMode(VoiceMode.THINKING);
  }, []);

  /**
   * Initialize WebSocket connection
   */
  const initWebSocket = useCallback(
    (tableId, onAudioChunk) => {
      const wsUrl = `${config.WS_URL}/ws/voice/${tableId}`;

      const ws = new WebSocket(wsUrl);
      ws.binaryType = "arraybuffer";

      ws.onopen = () => {
        console.log("✅ WebSocket connected (full-duplex mode)");
        console.log("📊 WebSocket state:", ws.readyState, "(1=OPEN)");
        setError(null);
      };

      ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          // Binary audio chunk from TTS
          if (onAudioChunk) {
            onAudioChunk(event.data);
          }
        } else {
          // JSON message
          const message = JSON.parse(event.data);
          handleWebSocketMessage(message);
        }
      };

      ws.onerror = (error) => {
        console.error("❌ WebSocket error:", error);
        setError("Connection error");
      };

      ws.onclose = (event) => {
        console.log(
          "🔌 WebSocket closed - Code:",
          event.code,
          "Reason:",
          event.reason || "No reason",
          "Clean:",
          event.wasClean,
        );

        // Handle specific close codes
        if (event.code === 4004) {
          setError("Masa bulunamadı. QR kodu geçersiz olabilir.");
        } else if (event.code === 1006) {
          setError(
            "Bağlantı beklenmedik şekilde kesildi. Backend çalışıyor mu?",
          );
        } else if (!event.wasClean) {
          setError(`Bağlantı hatası (Kod: ${event.code})`);
        }

        setMode(VoiceMode.IDLE);
      };

      wsRef.current = ws;
      return ws;
    },
    [handleWebSocketMessage],
  );

  /**
   * Set MediaRecorder ref (called from parent component)
   */
  const setMediaRecorder = useCallback((recorder) => {
    mediaRecorderRef.current = recorder;
  }, []);

  /**
   * Set media stream ref (called from parent component)
   */
  const setStream = useCallback((stream) => {
    streamRef.current = stream;
  }, []);

  /**
   * Start listening for user speech
   */
  const startListening = useCallback(
    async (stream) => {
      try {
        streamRef.current = stream;
        setMode(VoiceMode.LISTENING);
        setPartialTranscript("");
        setFinalTranscript("");
        setAiResponse("");
        setError(null);

        // Initialize VAD
        vadRef.current = new VoiceActivityDetector({
          silenceThreshold: 0.01,
          silenceDuration: 1500, // Increased from 500ms to 1500ms for better stability
        });

        // Initialize audio analyser for VAD
        if (!audioContextRef.current) {
          audioContextRef.current = new AudioContext();
        }
        const audioContext = audioContextRef.current;
        const source = audioContext.createMediaStreamSource(stream);
        analyserRef.current = audioContext.createAnalyser();
        source.connect(analyserRef.current);

        vadRef.current.initializeAnalyzer(stream);

        // Start VAD polling (check for silence every 50ms for faster detection)
        const vadIntervalId = setInterval(() => {
          if (vadRef.current) {
            const vadStatus = vadRef.current.analyzeAudioLevel();
            if (vadStatus === "SILENCE_DETECTED") {
              console.log("🔇 Speech ended (VAD detected silence)");
              clearInterval(vadIntervalId);
              stopListening();
            }
          }
        }, 50);

        // Store interval ID for cleanup
        vadRef.current.intervalId = vadIntervalId;
      } catch (error) {
        console.error("❌ Error starting listening:", error);
        setError(error.message);
        setMode(VoiceMode.IDLE);
      }
    },
    [stopListening],
  );

  /**
   * Send audio chunk to server
   */
  const sendAudioChunk = useCallback(async (chunk) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      // Convert Blob to ArrayBuffer for WebSocket binary transmission
      const arrayBuffer =
        chunk instanceof Blob ? await chunk.arrayBuffer() : chunk;
      wsRef.current.send(arrayBuffer);
    } else {
      console.warn(
        "⚠️ WebSocket not ready, chunk not sent. State:",
        wsRef.current?.readyState,
      );
    }
  }, []);

  /**
   * Cleanup resources
   */
  const cleanup = useCallback(() => {
    stopBargeInDetection();

    if (vadRef.current) {
      // Clear VAD polling interval
      if (vadRef.current.intervalId) {
        clearInterval(vadRef.current.intervalId);
      }
      vadRef.current.cleanup();
      vadRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    analyserRef.current = null;
    setMode(VoiceMode.IDLE);
  }, [stopBargeInDetection]);

  return {
    mode,
    partialTranscript,
    finalTranscript,
    aiResponse,
    error,
    initWebSocket,
    startListening,
    stopListening,
    sendAudioChunk,
    handleBargeIn,
    cleanup,
    setMediaRecorder,
    setStream,
    wsRef,
  };
}
