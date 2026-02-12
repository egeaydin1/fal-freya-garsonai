import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import VoiceButton from "../components/VoiceButton";
import StatusBadge from "../components/StatusBadge";
import TranscriptDisplay from "../components/TranscriptDisplay";
import AIResponse from "../components/AIResponse";
import Waveform from "../components/Waveform";
import { VoiceActivityDetector } from "../utils/VoiceActivityDetector";
import { AudioCompressor } from "../utils/AudioCompressor";
import { StreamingAudioPlayer } from "../utils/StreamingAudioPlayer";

export default function VoiceAI() {
  const { qrToken } = useParams();
  const navigate = useNavigate();
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [aiResponse, setAiResponse] = useState("");
  const [status, setStatus] = useState("idle");
  const [isPlaying, setIsPlaying] = useState(false);

  const wsRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioRef = useRef(null);
  const audioChunksRef = useRef([]);
  const vadRef = useRef(null);
  const vadIntervalRef = useRef(null);
  const compressorRef = useRef(new AudioCompressor());
  const streamingPlayerRef = useRef(new StreamingAudioPlayer());

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (mediaRecorderRef.current) {
        mediaRecorderRef.current.stop();
      }
      if (vadRef.current) {
        vadRef.current.cleanup();
      }
      if (vadIntervalRef.current) {
        clearInterval(vadIntervalRef.current);
      }
    };
  }, []);

  const connectWebSocket = () => {
    const ws = new WebSocket(`ws://localhost:8000/ws/voice/${qrToken}`);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("WebSocket connected");
      setStatus("connected");
    };

    ws.onmessage = async (event) => {
      // Handle binary audio chunks - STREAMING PCM16 from TTS
      if (event.data instanceof Blob) {
        const arrayBuffer = await event.data.arrayBuffer();

        // Add PCM chunk to streaming player (plays immediately)
        await streamingPlayerRef.current.addPCMChunk(arrayBuffer);

        console.log(`🎵 TTS chunk received: ${arrayBuffer.byteLength} bytes`);
        return;
      }

      // Handle JSON messages
      const data = JSON.parse(event.data);
      console.log("WS message:", data);

      switch (data.type) {
        case "status":
          setStatus(data.message);
          break;
        case "transcript":
          setTranscript(data.text);
          break;
        case "ai_token":
          // Parse JSON and extract spoken_response
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
          console.log("AI complete:", data.data);
          break;
        case "tts_start":
          setIsPlaying(true);
          // Reset streaming player for new session
          streamingPlayerRef.current.reset();
          console.log("🎧 TTS streaming started");
          break;
        case "tts_complete":
          // Finalize streaming (let remaining chunks play out)
          streamingPlayerRef.current.finalize();
          setIsPlaying(false);
          setStatus("idle");
          console.log("✅ TTS streaming complete");
          break;
        case "error":
          setStatus(`Error: ${data.message}`);
          break;
          setIsPlaying(true);
          // Reset audio player for new session
          audioPlayerRef.current.reset();
          break;
        case "tts_complete":
          // Finalize playback (ensure all chunks play)
          audioPlayerRef.current.finalize();
          setIsPlaying(false);
          setStatus("idle");
          break;
        case "error":
          setStatus(`Error: ${data.message}`);
          break;
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      setStatus("error");
    };

    ws.onclose = () => {
      console.log("WebSocket closed");
      setStatus("disconnected");
    };
  };

  const playAudio = async (audioBlob) => {
    try {
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);

      audio.onended = () => {
        URL.revokeObjectURL(audioUrl);
      };

      await audio.play();
    } catch (err) {
      console.error("Audio playback error:", err);
    }
  };

  const startListening = async () => {
    try {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        connectWebSocket();
        await new Promise((resolve) => setTimeout(resolve, 500));
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      // Initialize VAD
      if (!vadRef.current) {
        vadRef.current = new VoiceActivityDetector({
          silenceThreshold: 0.01,
          silenceDuration: 1500,
        });
      }
      vadRef.current.initializeAnalyzer(stream);
      vadRef.current.reset();

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: "audio/webm;codecs=opus",
        audioBitsPerSecond: 16000, // 16kbps optimized for voice
      });
      mediaRecorderRef.current = mediaRecorder;

      // Clear previous chunks
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          // Accumulate chunks instead of sending immediately
          audioChunksRef.current.push(event.data);
        }
      };

      // Start VAD monitoring
      vadIntervalRef.current = setInterval(() => {
        const vadStatus = vadRef.current.analyzeAudioLevel();
        if (vadStatus === "SILENCE_DETECTED") {
          console.log("🎯 VAD: Auto-stopping due to silence");
          stopListening();
        }
      }, 100); // Check every 100ms

      mediaRecorder.start(1000);
      setIsListening(true);
      setTranscript("");
      setAiResponse("");
      setStatus("listening");
    } catch (err) {
      console.error("Microphone error:", err);
      alert("Cannot access microphone");
    }
  };

  const stopListening = async () => {
    // Clear VAD interval
    if (vadIntervalRef.current) {
      clearInterval(vadIntervalRef.current);
      vadIntervalRef.current = null;
    }

    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream
        .getTracks()
        .forEach((track) => track.stop());
    }
    setIsListening(false);
    setStatus("processing");

    // Send accumulated audio as single blob with compression
    if (
      audioChunksRef.current.length > 0 &&
      wsRef.current?.readyState === WebSocket.OPEN
    ) {
      const fullAudioBlob = new Blob(audioChunksRef.current, {
        type: "audio/webm",
      });

      // Compress audio before sending
      const compressedBlob =
        await compressorRef.current.compressAudio(fullAudioBlob);

      wsRef.current.send(compressedBlob);
      audioChunksRef.current = [];
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <div className="navbar bg-base-100 shadow-lg">
        <div className="flex-1">
          <a className="btn btn-ghost text-xl">Voice AI</a>
        </div>
        <div className="flex-none">
          <button
            className="btn btn-ghost"
            onClick={() => navigate(`/menu/${qrToken}`)}
          >
            Back to Menu
          </button>
        </div>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center p-4">
        <div className="card w-full max-w-2xl bg-base-100 shadow-2xl">
          <div className="card-body items-center text-center">
            <h2 className="card-title text-3xl mb-4">GarsonAI</h2>

            <VoiceButton isListening={isListening} isPlaying={isPlaying} />

            <StatusBadge status={status} />

            {!isListening ? (
              <button
                className="btn btn-primary btn-lg"
                onClick={startListening}
              >
                Start Talking
              </button>
            ) : (
              <button className="btn btn-error btn-lg" onClick={stopListening}>
                Stop
              </button>
            )}

            <TranscriptDisplay transcript={transcript} />

            <AIResponse response={aiResponse} />

            <Waveform isPlaying={isPlaying} />
          </div>
        </div>

        <div className="mt-6 text-center text-sm opacity-70">
          <p>Speak naturally to place your order</p>
          <p>Example: "I'd like two pizzas and a cola"</p>
        </div>
      </div>
    </div>
  );
}
