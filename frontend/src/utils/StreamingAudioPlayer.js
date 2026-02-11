/**
 * Streaming Audio Player for Real-Time PCM16 Playback
 * Plays audio chunks as they arrive from TTS streaming endpoint
 * No buffering delay - immediate playback
 */
export class StreamingAudioPlayer {
  constructor(options = {}) {
    this.sampleRate = options.sampleRate || 16000; // 16kHz PCM
    this.audioContext = null;
    this.audioQueue = [];
    this.isPlaying = false;
    this.nextStartTime = 0;
  }

  /**
   * Initialize audio context (call on user interaction)
   */
  async initialize() {
    if (!this.audioContext) {
      this.audioContext = new (
        window.AudioContext || window.webkitAudioContext
      )({
        sampleRate: this.sampleRate,
      });
      
      console.log("🎧 StreamingAudioPlayer: Initialized");
    }
  }

  /**
   * Add PCM16 chunk and play immediately
   * @param {ArrayBuffer} pcmBytes - Raw PCM16 audio data
   */
  async addPCMChunk(pcmBytes) {
    if (!this.audioContext) {
      await this.initialize();
    }

    try {
      // Convert PCM16 to AudioBuffer
      const audioBuffer = await this.pcmToAudioBuffer(pcmBytes);
      
      // Add to queue
      this.audioQueue.push(audioBuffer);

      // Start playback if not already playing
      if (!this.isPlaying) {
        this.isPlaying = true;
        this.nextStartTime = this.audioContext.currentTime;
        this.playNext();
      }

      console.log(
        `🎵 Chunk added: ${audioBuffer.duration.toFixed(3)}s (queue: ${this.audioQueue.length})`,
      );
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
      // Queue empty, wait for more chunks
      this.isPlaying = false;
      console.log("⏸️ Playback paused (waiting for chunks)");
      return;
    }

    const audioBuffer = this.audioQueue.shift();

    // Create buffer source
    const source = this.audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(this.audioContext.destination);

    // Schedule at precise time for gapless playback
    const currentTime = this.audioContext.currentTime;
    const startTime = Math.max(currentTime, this.nextStartTime);
    
    source.start(startTime);

    // Update next start time
    this.nextStartTime = startTime + audioBuffer.duration;

    // Schedule next chunk
    source.onended = () => {
      this.playNext();
    };

    console.log(
      `▶️ Playing chunk at ${startTime.toFixed(3)}s (${audioBuffer.duration.toFixed(3)}s)`,
    );
  }

  /**
   * Stop playback and clear queue
   */
  stop() {
    this.isPlaying = false;
    this.audioQueue = [];
    this.nextStartTime = 0;
    
    if (this.audioContext) {
      this.audioContext.suspend();
    }
    
    console.log("🛑 Playback stopped");
  }

  /**
   * Reset for new session
   */
  reset() {
    this.stop();
    
    if (this.audioContext) {
      this.audioContext.resume();
    }
    
    console.log("🔄 Player reset");
  }

  /**
   * Finalize playback (no more chunks coming)
   */
  finalize() {
    // Just let the queue play out
    console.log("✅ Streaming finalized, playing remaining chunks");
  }
}
