import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import VoiceButton from "../components/VoiceButton";
import StatusBadge from "../components/StatusBadge";
import TranscriptDisplay from "../components/TranscriptDisplay";
import AIResponse from "../components/AIResponse";
import Waveform from "../components/Waveform";
import useVoiceSession, { VoiceMode } from "../hooks/useVoiceSession";
import { StreamingAudioPlayer } from "../utils/StreamingAudioPlayer";

export default function VoiceAI() {
  const { qrToken } = useParams();
  const navigate = useNavigate();
  
  // Full-duplex voice session hook
  const {
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
    wsRef
  } = useVoiceSession();
  
  const [displayedTranscript, setDisplayedTranscript] = useState("");
  const [displayedAiResponse, setDisplayedAiResponse] = useState("");
  
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const streamingPlayerRef = useRef(new StreamingAudioPlayer());

  // Update displayed transcript (prefer final over partial)
  useEffect(() => {
    if (finalTranscript) {
      setDisplayedTranscript(finalTranscript);
    } else if (partialTranscript) {
      setDisplayedTranscript(partialTranscript + "...");
    }
  }, [partialTranscript, finalTranscript]);
  
  // Update displayed AI response
  useEffect(() => {
    if (aiResponse) {
      // Try to parse JSON structure if present
      try {
        if (aiResponse.includes("{") && aiResponse.includes("}")) {
          const jsonStart = aiResponse.indexOf("{");
          const jsonEnd = aiResponse.lastIndexOf("}") + 1;
          const jsonStr = aiResponse.substring(jsonStart, jsonEnd);
          const parsed = JSON.parse(jsonStr);
          setDisplayedAiResponse(parsed.spoken_response || aiResponse);
        } else {
          setDisplayedAiResponse(aiResponse);
        }
      } catch (e) {
        setDisplayedAiResponse(aiResponse);
      }
    }
  }, [aiResponse]);
  
  // Map VoiceMode to legacy status for compatibility
  const status = {
    [VoiceMode.IDLE]: "idle",
    [VoiceMode.LISTENING]: "listening", 
    [VoiceMode.THINKING]: "processing",
    [VoiceMode.SPEAKING]: "speaking"
  }[mode] || "idle";
  
  const isListening = mode === VoiceMode.LISTENING;
  const isPlaying = mode === VoiceMode.SPEAKING;

  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanup();
      if (mediaRecorderRef.current) {
        mediaRecorderRef.current.stop();
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, [cleanup]);
  
  // Initialize WebSocket connection
  useEffect(() => {
    if (qrToken) {
      // Handle audio chunks from TTS
      const handleAudioChunk = async (arrayBuffer) => {
        await streamingPlayerRef.current.addPCMChunk(arrayBuffer);
        console.log(`🎵 TTS chunk: ${arrayBuffer.byteLength} bytes`);
      };
      
      initWebSocket(qrToken, handleAudioChunk);
      
      // Wait for WebSocket to be ready before allowing recording
      const checkInterval = setInterval(() => {
        if (wsRef.current?.readyState === 1) {
          console.log('✅ WebSocket ready for recording');
          clearInterval(checkInterval);
        }
      }, 100);
      
      // Cleanup on unmount or qrToken change
      return () => {
        clearInterval(checkInterval);
        if (wsRef.current) {
          wsRef.current.close();
        }
      };
    }
  }, [qrToken, initWebSocket]);

  // Start voice recording
  const handleStartListening = async () => {
    try {
      // Wait for WebSocket to be ready
      if (!wsRef.current || wsRef.current.readyState !== 1) {
        console.warn('⚠️ WebSocket not ready, waiting...');
        await new Promise((resolve) => {
          const interval = setInterval(() => {
            if (wsRef.current?.readyState === 1) {
              clearInterval(interval);
              resolve();
            }
          }, 100);
          
          // Timeout after 5 seconds
          setTimeout(() => {
            clearInterval(interval);
            resolve();
          }, 5000);
        });
      }
      
      if (wsRef.current?.readyState !== 1) {
        alert('WebSocket bağlantısı hazır değil. Lütfen sayfayı yenileyin.');
        return;
      }
      
      console.log('🎤 Starting recording with WebSocket state:', wsRef.current.readyState);
      
      // Get audio stream with optimized constraints
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          channelCount: 1,      // Mono
          sampleRate: 16000,    // 16kHz
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        } 
      });
      
      // Setup MediaRecorder for chunk streaming
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: "audio/webm;codecs=opus",
        audioBitsPerSecond: 16000, // 16kbps low bitrate
      });
      mediaRecorderRef.current = mediaRecorder;
      
      // Pass refs to hook
      setMediaRecorder(mediaRecorder);
      setStream(stream);
      
      // Initialize VAD and start listening
      await startListening(stream);
      
      mediaRecorder.ondataavailable = async (event) => {
        if (event.data.size > 0) {
          // Send 500ms chunks to server for incremental STT
          console.log(`📤 Streaming chunk: ${event.data.size} bytes, WS state: ${wsRef.current?.readyState}`);
          await sendAudioChunk(event.data);
        }
      };
      
      // Start recording with 500ms chunks
      mediaRecorder.start(500);
      
      console.log("✅ Full-duplex voice session started");
    } catch (err) {
      console.error("❌ Microphone error:", err);
      alert("Cannot access microphone: " + err.message);
    }
  };
  
  // Stop voice recording
  const handleStopListening = async () => {
    stopListening();
  };
  
  // Handle barge-in (interrupt AI and restart listening)
  const handleInterrupt = async () => {
    // Stop AI playback and send interrupt
    handleBargeIn();
    
    // Wait a bit for interrupt to be processed
    await new Promise(resolve => setTimeout(resolve, 100));
    
    // Restart listening immediately
    handleStartListening();
  };

  return (
    <div className="min-h-screen flex flex-col">
      <div className="navbar bg-base-100 shadow-lg">
        <div className="flex-1">
          <a className="btn btn-ghost text-xl">Sesli Sipariş (Manuel Kontrol)</a>
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
            
            {/* Voice Mode Badge */}
            <div className="badge badge-lg badge-primary mb-2">
              Mode: {mode.toUpperCase()}
            </div>

            <VoiceButton isListening={isListening} isPlaying={isPlaying} />

            <StatusBadge status={status} />

            {/* Button logic: IDLE/THINKING -> Start button, LISTENING -> Stop button, SPEAKING -> Interrupt button */}
            {mode === VoiceMode.IDLE || mode === VoiceMode.THINKING ? (
              <button
                className="btn btn-primary btn-lg"
                onClick={handleStartListening}
                disabled={mode === VoiceMode.THINKING}
              >
                {mode === VoiceMode.THINKING ? 'İşleniyor...' : 'Konuşmaya Başla'}
              </button>
            ) : mode === VoiceMode.LISTENING ? (
              <button 
                className="btn btn-error btn-lg" 
                onClick={handleStopListening}
              >
                Durdur
              </button>
            ) : mode === VoiceMode.SPEAKING ? (
              <button 
                className="btn btn-warning btn-lg" 
                onClick={handleInterrupt}
              >
                Kes / Yeniden Konuş
              </button>
            ) : null}
            
            {/* Partial transcript indicator */}
            {partialTranscript && !finalTranscript && (
              <div className="alert alert-info shadow-lg mt-4">
                <div>
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" className="stroke-current flex-shrink-0 w-6 h-6"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                  <span className="text-sm">Incremental STT active...</span>
                </div>
              </div>
            )}

            <TranscriptDisplay transcript={displayedTranscript} />

            <AIResponse response={displayedAiResponse} />

            <Waveform isPlaying={isPlaying} />
            
            {/* Error display */}
            {error && (
              <div className="alert alert-error shadow-lg mt-4">
                <div>
                  <svg xmlns="http://www.w3.org/2000/svg" className="stroke-current flex-shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                  <span>{error}</span>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="mt-6 text-center text-sm opacity-70">
          <p>✨ Manuel kontrol modu - İstediğiniz zaman konuşun</p>
          <p>🎤 "Konuşmaya Başla" butonuna basın ve siparişinizi verin</p>
          <p>🛑 AI konuşurken "Kes / Yeniden Konuş" ile sözünü kesebilirsiniz</p>
        </div>
      </div>
    </div>
  );
}
