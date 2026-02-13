/**
 * Voice Activity Detection (VAD) v2
 * - Configurable silence trimming
 * - Speaking detection with RMS threshold
 * - 100ms polling intervals
 * - Clean start/stop lifecycle
 */
export class VoiceActivityDetector {
  constructor(stream, options = {}) {
    this.stream = stream;
    this.silenceThreshold = options.silenceThreshold || 0.012;
    this.silenceDuration = options.silenceDuration || 1500; // 1.5s silence → stop
    this.checkInterval = options.checkInterval || 100; // 100ms polling
    this.silenceStart = null;
    this.audioContext = null;
    this.analyser = null;
    this.dataArray = null;
    this._speaking = false;
    this._speechStarted = false;
  }

  /** Initialize audio analyser from the media stream. */
  async initialize() {
    this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = 2048;
    this.analyser.smoothingTimeConstant = 0.3;

    const source = this.audioContext.createMediaStreamSource(this.stream);
    source.connect(this.analyser);

    this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
  }

  /** Returns true if voice is currently detected. */
  isSpeaking() {
    if (!this.analyser || !this.dataArray) return true; // fail-open

    this.analyser.getByteTimeDomainData(this.dataArray);

    let sum = 0;
    for (let i = 0; i < this.dataArray.length; i++) {
      const n = (this.dataArray[i] - 128) / 128;
      sum += n * n;
    }
    const rms = Math.sqrt(sum / this.dataArray.length);

    if (rms >= this.silenceThreshold) {
      this.silenceStart = null;
      this._speaking = true;
      this._speechStarted = true;
      return true;
    }

    // Below threshold
    if (!this._speechStarted) return false; // never started speaking

    if (!this.silenceStart) {
      this.silenceStart = Date.now();
      return true; // grace period
    }

    if (Date.now() - this.silenceStart < this.silenceDuration) {
      return true; // still within grace
    }

    // Silence exceeded threshold
    console.log("🔇 VAD: Silence detected, auto-stopping");
    return false;
  }

  /** Whether user has started speaking at all. */
  hasSpeechStarted() {
    return this._speechStarted;
  }

  /** Clean up resources. */
  cleanup() {
    if (this.audioContext) {
      this.audioContext.close().catch(() => {});
      this.audioContext = null;
      this.analyser = null;
      this.dataArray = null;
    }
    this.silenceStart = null;
    this._speaking = false;
    this._speechStarted = false;
  }
}
