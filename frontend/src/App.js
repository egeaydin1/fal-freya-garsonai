import React, { useState, useRef, useEffect } from "react";
import "./App.css";

function App() {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [aiResponse, setAiResponse] = useState("");
  const [currentSegment, setCurrentSegment] = useState("");
  const [status, setStatus] = useState("Konuşmak için butona bas");

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const audioQueueRef = useRef([]);
  const isPlayingRef = useRef(false);

  // Ses kaydı başlat
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (event) => {
        audioChunksRef.current.push(event.data);
      };

      mediaRecorderRef.current.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, {
          type: "audio/wav",
        });
        await sendAudioToBackend(audioBlob);
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorderRef.current.start();
      setIsRecording(true);
      setStatus("Konuşuyor... Bitirmek için tekrar bas");
    } catch (error) {
      console.error("Mikrofon erişim hatası:", error);
      setStatus("Mikrofon erişimi reddedildi");
    }
  };

  // Ses kaydını durdur
  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      setStatus("İşleniyor...");
      setIsProcessing(true);
    }
  };

  // Butona tıklama
  const handleButtonClick = () => {
    if (isRecording) {
      stopRecording();
    } else if (!isProcessing) {
      setAiResponse("");
      setCurrentSegment("");
      startRecording();
    }
  };

  // Ses dosyasını backend'e gönder
  const sendAudioToBackend = async (audioBlob) => {
    try {
      setStatus("AI düşünüyor...");

      // FormData ile ses dosyasını gönder
      const formData = new FormData();
      formData.append("audio", audioBlob, "recording.wav");

      // 1. Chat başlat ve task_id al
      const response = await fetch("http://localhost:8000/api/ai/chat", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      const taskId = data.task_id;

      // 2. Stream endpoint'ine bağlan
      const streamResponse = await fetch(
        `http://localhost:8000/api/ai/stream/${taskId}`,
      );

      if (!streamResponse.ok) {
        throw new Error(`Stream error! status: ${streamResponse.status}`);
      }

      const reader = streamResponse.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      // Stream'den gelen verileri işle
      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop(); // Son tamamlanmamış satırı sakla

        for (const line of lines) {
          if (line.trim() === "") continue;

          try {
            const message = JSON.parse(line);

            if (message.type === "ai_response") {
              setAiResponse(message.data);
              setStatus("AI cevap verdi, sesli cevap hazırlanıyor...");
            } else if (message.type === "audio_segment") {
              audioQueueRef.current.push(message.data);
              if (!isPlayingRef.current) {
                playNextSegment();
              }
            } else if (message.type === "complete") {
              if (audioQueueRef.current.length === 0 && !isPlayingRef.current) {
                setStatus("Tamamlandı! Yeni konuşma için butona bas");
                setIsProcessing(false);
              }
            } else if (message.type === "error") {
              throw new Error(message.data);
            }
          } catch (parseError) {
            console.error("JSON parse hatası:", parseError, "Line:", line);
          }
        }
      }
    } catch (error) {
      console.error("Backend hatası:", error);
      setStatus("Hata oluştu: " + error.message);
      setIsProcessing(false);
    }
  };

  // Ses segmentlerini sırayla oynat
  const playNextSegment = async () => {
    if (audioQueueRef.current.length === 0) {
      isPlayingRef.current = false;
      setStatus("Tamamlandı! Yeni konuşma için butona bas");
      setIsProcessing(false);
      return;
    }

    isPlayingRef.current = true;
    const segment = audioQueueRef.current.shift();

    setCurrentSegment(segment.text);
    setStatus(`Konuşuyor: ${segment.text.substring(0, 50)}...`);

    const audio = new Audio(segment.audio_url);

    audio.onended = () => {
      playNextSegment();
    };

    audio.onerror = (e) => {
      console.error("Ses oynatma hatası:", e);
      playNextSegment();
    };

    try {
      await audio.play();
    } catch (e) {
      console.error("Play hatası:", e);
      playNextSegment();
    }
  };

  return (
    <div className="App">
      <div className="container">
        <h1 className="title">🎙️ GarsonAI</h1>
        <p className="subtitle">Sesli Asistan</p>

        <div className="status-box">
          <p className="status">{status}</p>
        </div>

        {aiResponse && (
          <div className="response-box">
            <h3>AI Cevabı:</h3>
            <p>{aiResponse}</p>
          </div>
        )}

        {currentSegment && (
          <div className="segment-box">
            <p className="segment-text">{currentSegment}</p>
          </div>
        )}

        <button
          className={`record-button ${isRecording ? "recording" : ""} ${isProcessing ? "disabled" : ""}`}
          onClick={handleButtonClick}
          disabled={isProcessing && !isRecording}
        >
          {isRecording
            ? "⏹️ Durdur"
            : isProcessing
              ? "⏳ İşleniyor..."
              : "🎤 Konuş"}
        </button>

        <div className="instructions">
          <p>1. Butona basarak kaydı başlat</p>
          <p>2. Konuş</p>
          <p>3. Bitirmek için tekrar bas</p>
          <p>4. AI cevabı dinle</p>
        </div>
      </div>
    </div>
  );
}

export default App;
