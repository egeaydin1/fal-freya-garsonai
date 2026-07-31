/**
 * Voice Activity Detection (VAD) for automatic silence detection
 * Reduces latency by ~2s by eliminating manual stop button wait
 */
export class VoiceActivityDetector {
  constructor(options = {}) {
    this.silenceThreshold = options.silenceThreshold || 0.01; // Amplitude threshold
    this.silenceDuration = options.silenceDuration || 1500; // 1.5 seconds of silence
    this.silenceStart = null;
    this.audioContext = null;
    this.analyser = null;
    this.dataArray = null;
  }

  /**
   * Initialize audio analysis context
   */
  initializeAnalyzer(stream) {
    this.audioContext = new (
      window.AudioContext || window.webkitAudioContext
    )();
    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = 2048;

    const source = this.audioContext.createMediaStreamSource(stream);
    source.connect(this.analyser);

    const bufferLength = this.analyser.frequencyBinCount;
    this.dataArray = new Uint8Array(bufferLength);
  }

  /**
   * Analyze current audio level from MediaRecorder data
   * Returns 'SILENCE_DETECTED' when silence threshold is met
   */
  analyzeAudioLevel() {
    if (!this.analyser || !this.dataArray) {
      return "SPEAKING";
    }

    // Get time domain data (waveform)
    this.analyser.getByteTimeDomainData(this.dataArray);

    // Calculate RMS (Root Mean Square) amplitude
    let sum = 0;
    for (let i = 0; i < this.dataArray.length; i++) {
      const normalized = (this.dataArray[i] - 128) / 128; // Normalize to -1 to 1
      sum += normalized * normalized;
    }
    const rms = Math.sqrt(sum / this.dataArray.length);

    // Check if below silence threshold
    if (rms < this.silenceThreshold) {
      if (!this.silenceStart) {
        this.silenceStart = Date.now();
      } else if (Date.now() - this.silenceStart > this.silenceDuration) {
        console.log(
          `🔇 VAD: Silence detected (${this.silenceDuration}ms), auto-stopping`,
        );
        return "SILENCE_DETECTED";
      }
    } else {
      // Reset silence timer on voice activity
      this.silenceStart = null;
    }

    return "SPEAKING";
  }

  /**
   * Clean up audio context
   */
  cleanup() {
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
      this.analyser = null;
      this.dataArray = null;
    }
    this.silenceStart = null;
  }

  /**
   * Reset silence detection state
   */
  reset() {
    this.silenceStart = null;
  }
}
