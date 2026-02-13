/**
 * Streaming Audio Player v2 for Real-Time PCM16 Playback
 * - Plays first chunk IMMEDIATELY (no buffering)
 * - Gapless playback via scheduled AudioBufferSourceNodes
 * - Fires onPlaybackComplete when all chunks are done
 * - Tracks playing state for VAD coordination
 */
export class StreamingAudioPlayer {
  constructor(options = {}) {
    this.sampleRate = options.sampleRate || 16000;
    this.audioContext = null;
    this.audioQueue = [];
    this.isPlaying = false;
    this.nextStartTime = 0;
    this.onPlaybackComplete = options.onPlaybackComplete || null;
    this._finalized = false;
    this._chunksPlayed = 0;
    this._totalChunks = 0;
  }

  async initialize() {
    if (!this.audioContext) {
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: this.sampleRate,
      });
      console.log("🎧 StreamingAudioPlayer: Initialized");
    }
  }

  async addPCMChunk(pcmBytes) {
    if (!this.audioContext) await this.initialize();

    if (this.audioContext.state === "suspended") {
      await this.audioContext.resume();
    }

    try {
      const audioBuffer = await this.pcmToAudioBuffer(pcmBytes);
      this.audioQueue.push(audioBuffer);
      this._totalChunks++;

      if (!this.isPlaying) {
        this.isPlaying = true;
        this.nextStartTime = this.audioContext.currentTime;
        this.playNext();
      }
    } catch (error) {
      console.error("❌ Error processing PCM chunk:", error);
    }
  }

  /**
   * Convert PCM16 bytes to AudioBuffer
   * @param {ArrayBuffer} pcmBytes - Raw PCM16 (16-bit signed integers)
   * @returns {AudioBuffer}
   */
  async pcmToAudioBuffer(pcmBytes) {
    // PCM16 = 16-bit signed integers (Int16Array)
    const samples = new Int16Array(pcmBytes);

    // Convert to Float32Array (Web Audio API format)
    const floatSamples = new Float32Array(samples.length);
    for (let i = 0; i < samples.length; i++) {
      floatSamples[i] = samples[i] / 32768.0; // Normalize to [-1, 1]
    }

    // Create AudioBuffer
    const audioBuffer = this.audioContext.createBuffer(
      1, // Mono
      floatSamples.length,
      this.sampleRate,
    );

    // Set channel data
    audioBuffer.getChannelData(0).set(floatSamples);

    return audioBuffer;
  }

  /**
   * Play next chunk in queue (gapless playback)
   */
  playNext() {
    if (this.audioQueue.length === 0) {
      // Queue empty
      if (this._finalized) {
        // All chunks played, we're truly done
        this.isPlaying = false;
        console.log("✅ Playback complete");
        if (this.onPlaybackComplete) this.onPlaybackComplete();
      } else {
        this.isPlaying = false;
      }
      return;
    }

    const audioBuffer = this.audioQueue.shift();
    const source = this.audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(this.audioContext.destination);

    const currentTime = this.audioContext.currentTime;
    const startTime = Math.max(currentTime, this.nextStartTime);
    source.start(startTime);
    this.nextStartTime = startTime + audioBuffer.duration;
    this._chunksPlayed++;

    source.onended = () => {
      this.playNext();
    };
  }

  /**
   * Stop playback and clear queue
   */
  stop() {
    this.isPlaying = false;
    this.audioQueue = [];
    this.nextStartTime = 0;
    this._finalized = false;
    this._chunksPlayed = 0;
    this._totalChunks = 0;

    if (this.audioContext) {
      this.audioContext.suspend();
    }
  }

  reset() {
    this.stop();
    if (this.audioContext) {
      this.audioContext.resume();
    }
  }

  finalize() {
    this._finalized = true;
    // If queue is already empty and not playing, fire complete immediately
    if (!this.isPlaying && this.audioQueue.length === 0) {
      console.log("✅ Playback complete (finalized with empty queue)");
      if (this.onPlaybackComplete) this.onPlaybackComplete();
    }
  }
}
