/**
 * Smart Audio Player with buffering to prevent stuttering
 * Buffers minimum 500ms audio before playback starts
 */
export class SmartAudioPlayer {
  constructor(options = {}) {
    this.audioContext = new (
      window.AudioContext || window.webkitAudioContext
    )();
    this.minBufferDuration = options.minBufferDuration || 0.5; // 500ms
    this.buffer = [];
    this.isPlaying = false;
    this.currentSourceIndex = 0;
    this.playbackStartTime = 0;
  }

  /**
   * Add audio chunk to buffer
   * Will auto-start playback when sufficient buffer accumulated
   */
  async addChunk(audioBlob) {
    try {
      // Convert blob to array buffer
      const arrayBuffer = await audioBlob.arrayBuffer();

      // Decode audio data
      const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);

      // Add to buffer
      this.buffer.push(audioBuffer);

      console.log(
        `🎵 Buffer: Added chunk (${audioBuffer.duration.toFixed(2)}s), total: ${this.getTotalDuration().toFixed(2)}s`,
      );

      // Check if we have enough buffer to start
      if (!this.isPlaying && this.hasEnoughBuffer()) {
        console.log("✅ Sufficient buffer accumulated, starting playback");
        this.startPlayback();
      }
    } catch (error) {
      console.error("Error adding audio chunk:", error);
    }
  }

  /**
   * Check if we have enough buffered audio
   */
  hasEnoughBuffer() {
    const totalDuration = this.getTotalDuration();
    return totalDuration >= this.minBufferDuration;
  }

  /**
   * Get total duration of buffered audio
   */
  getTotalDuration() {
    return this.buffer.reduce((sum, buf) => sum + buf.duration, 0);
  }

  /**
   * Start smooth playback
   */
  async startPlayback() {
    if (this.isPlaying) return;

    this.isPlaying = true;
    this.playbackStartTime = this.audioContext.currentTime;

    console.log("🎧 Starting smooth playback");

    // Schedule all buffered chunks
    this.scheduleBufferedChunks();
  }

  /**
   * Schedule all buffered audio chunks for gapless playback
   */
  scheduleBufferedChunks() {
    let startTime = this.audioContext.currentTime;

    for (let i = this.currentSourceIndex; i < this.buffer.length; i++) {
      const audioBuffer = this.buffer[i];
      const source = this.audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(this.audioContext.destination);

      // Schedule at precise time for gapless playback
      source.start(startTime);

      // Update start time for next chunk
      startTime += audioBuffer.duration;

      // Track completion of last chunk
      if (i === this.buffer.length - 1) {
        source.onended = () => {
          console.log("✅ Playback complete");
          this.isPlaying = false;
        };
      }
    }

    this.currentSourceIndex = this.buffer.length;
  }

  /**
   * Add more chunks during playback (streaming)
   */
  async streamChunk(audioBlob) {
    await this.addChunk(audioBlob);

    // If already playing, schedule this new chunk
    if (this.isPlaying) {
      this.scheduleBufferedChunks();
    }
  }

  /**
   * Finalize and ensure all audio plays
   */
  finalize() {
    if (!this.isPlaying && this.buffer.length > 0) {
      // Force start even if buffer not full
      this.startPlayback();
    }
  }

  /**
   * Stop playback and clear buffer
   */
  stop() {
    // Stop audio context
    this.audioContext.suspend();

    this.isPlaying = false;
    this.buffer = [];
    this.currentSourceIndex = 0;

    console.log("🛑 Playback stopped");
  }

  /**
   * Reset for new playback session
   */
  reset() {
    this.stop();
    this.audioContext.resume();
  }
}
