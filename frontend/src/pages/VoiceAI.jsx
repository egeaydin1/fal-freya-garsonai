import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import VoiceButton from "../components/VoiceButton";
import StatusBadge from "../components/StatusBadge";
import TranscriptDisplay from "../components/TranscriptDisplay";
import AIResponse from "../components/AIResponse";
import Waveform from "../components/Waveform";

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
  const audioContextRef = useRef(null);

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (mediaRecorderRef.current) {
        mediaRecorderRef.current.stop();
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
      if (event.data instanceof Blob) {
        const audioBlob = event.data;
        playAudio(audioBlob);
      } else {
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
            setAiResponse(data.full_text);
            break;
          case "ai_complete":
            console.log("AI complete:", data.data);
            break;
          case "tts_start":
            setIsPlaying(true);
            break;
          case "tts_complete":
            setIsPlaying(false);
            setStatus("idle");
            break;
          case "error":
            setStatus(`Error: ${data.message}`);
            break;
        }
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
      if (!audioContextRef.current) {
        audioContextRef.current = new (
          window.AudioContext || window.webkitAudioContext
        )();
      }

      const arrayBuffer = await audioBlob.arrayBuffer();
      const audioBuffer =
        await audioContextRef.current.decodeAudioData(arrayBuffer);

      const source = audioContextRef.current.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContextRef.current.destination);
      source.start();
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
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (
          event.data.size > 0 &&
          wsRef.current?.readyState === WebSocket.OPEN
        ) {
          wsRef.current.send(event.data);
        }
      };

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

  const stopListening = () => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream
        .getTracks()
        .forEach((track) => track.stop());
    }
    setIsListening(false);
    setStatus("processing");
  };

  return (
    <div className="min-h-screen bg-base-200 flex flex-col">
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
            </div>

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

            {transcript && (
              <div className="w-full mt-6 p-4 bg-base-200 rounded-lg">
                <p className="text-sm opacity-70 mb-1">You said:</p>
                <p className="text-lg">{transcript}</p>
              </div>
            )}

            {aiResponse && (
              <div className="w-full mt-4 p-4 bg-primary/10 rounded-lg">
                <p className="text-sm opacity-70 mb-1">GarsonAI:</p>
                <p className="text-lg">{aiResponse}</p>
              </div>
            )}

            {isPlaying && (
              <div className="flex gap-1 mt-4">
                <div className="w-2 h-8 bg-success animate-pulse"></div>
                <div className="w-2 h-12 bg-success animate-pulse delay-75"></div>
                <div className="w-2 h-10 bg-success animate-pulse delay-150"></div>
                <div className="w-2 h-14 bg-success animate-pulse"></div>
                <div className="w-2 h-8 bg-success animate-pulse delay-75"></div>
              </div>
            )}
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
