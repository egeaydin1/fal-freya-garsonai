export class StreamingAudioPlayer {
  constructor(options = {}) {
    this.sampleRate = options.sampleRate || 16000; // 16kHz PCM
    this.audioContext = null;
    this.audioQueue = [];
    this.isPlaying = false;
    this.nextStartTime = 0;
    this.activeSource = null; // Track current playing node
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
    
    if (this.audioContext.state === 'suspended') {
      await this.audioContext.resume();
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
        
        // If nextStartTime is in the past, reset to current time
        const currentTime = this.audioContext.currentTime;
        if (this.nextStartTime < currentTime) {
          this.nextStartTime = currentTime;
        }
        
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
   */
  async pcmToAudioBuffer(pcmBytes) {
    const samples = new Int16Array(pcmBytes);
    const floatSamples = new Float32Array(samples.length);
    for (let i = 0; i < samples.length; i++) {
      floatSamples[i] = samples[i] / 32768.0;
    }

    const audioBuffer = this.audioContext.createBuffer(
      1,
      floatSamples.length,
      this.sampleRate,
    );
    audioBuffer.getChannelData(0).set(floatSamples);
    return audioBuffer;
  }

  /**
   * Play next chunk in queue (gapless playback)
   */
  playNext() {
    if (this.audioQueue.length === 0) {
      this.isPlaying = false;
      this.activeSource = null;
      console.log("⏸️ Playback paused (waiting for chunks)");
      return;
    }

    const audioBuffer = this.audioQueue.shift();
    const source = this.audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(this.audioContext.destination);

    const currentTime = this.audioContext.currentTime;
    const startTime = Math.max(currentTime, this.nextStartTime);

    source.start(startTime);
    this.activeSource = source;
    this.nextStartTime = startTime + audioBuffer.duration;

    source.onended = () => {
      // Only trigger if this was the source we expected to finish
      if (this.activeSource === source) {
        this.playNext();
      }
    };

    console.log(
      `▶️ Playing chunk at ${startTime.toFixed(3)}s (${audioBuffer.duration.toFixed(3)}s)`,
    );
  }

  /**
   * Stop playback and clear queue
   */
  stop() {
    console.log("🛑 Playback stopping...");
    this.isPlaying = false;
    this.audioQueue = [];
    this.nextStartTime = 0;

    if (this.activeSource) {
      try {
        this.activeSource.stop();
      } catch (e) {
        // Source might have already finished
      }
      this.activeSource = null;
    }
  }

  /**
   * Immediately stop playback and clear queue (for barge-in)
   */
  stopImmediately() {
    console.log("🛑 Playback stopped immediately (barge-in)");
    this.stop();
  }

  /**
   * Reset for new session
   */
  reset() {
    // DO NOT suspend context here, as it causes massive latency on next play
    this.isPlaying = false;
    this.audioQueue = [];
    this.nextStartTime = 0;
    
    if (this.activeSource) {
      try { this.activeSource.stop(); } catch (e) {}
      this.activeSource = null;
    }

    console.log("🔄 Player reset (context kept warm)");
  }

  /**
   * Finalize playback (no more chunks coming)
   */
  finalize() {
    console.log("✅ Streaming finalized, playing remaining chunks");
  }
}
