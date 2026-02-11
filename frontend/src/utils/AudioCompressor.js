/**
 * Audio Compression Utility
 * Reduces audio file size by ~30-40% for faster uploads
 * Optimizes for voice: mono channel, 16kHz sample rate, lower bitrate
 */
export class AudioCompressor {
  constructor() {
    this.targetSampleRate = 16000; // 16kHz is sufficient for voice
  }

  /**
   * Compress audio blob to mono, 16kHz
   * Reduces file size from ~40KB to ~25KB for typical 2-3s recording
   */
  async compressAudio(audioBlob) {
    try {
      console.log(
        `🔧 Compressor: Original size: ${(audioBlob.size / 1024).toFixed(2)}KB`,
      );

      // Create audio context with target sample rate
      const audioContext = new (
        window.AudioContext || window.webkitAudioContext
      )({
        sampleRate: this.targetSampleRate,
      });

      // Convert blob to array buffer
      const arrayBuffer = await audioBlob.arrayBuffer();

      // Decode audio data
      const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);

      // Convert to mono if stereo
      const monoBuffer = this.convertToMono(audioBuffer, audioContext);

      // Encode as Opus in WebM container
      const compressedBlob = await this.encodeAsWebM(monoBuffer, audioContext);

      console.log(
        `✅ Compressor: Compressed size: ${(compressedBlob.size / 1024).toFixed(2)}KB (${((1 - compressedBlob.size / audioBlob.size) * 100).toFixed(1)}% reduction)`,
      );

      // Cleanup
      await audioContext.close();

      return compressedBlob;
    } catch (error) {
      console.error("Compression failed, using original:", error);
      return audioBlob; // Fallback to original
    }
  }

  /**
   * Convert stereo to mono by averaging channels
   */
  convertToMono(audioBuffer, audioContext) {
    if (audioBuffer.numberOfChannels === 1) {
      return audioBuffer; // Already mono
    }

    // Create mono buffer
    const monoBuffer = audioContext.createBuffer(
      1, // Mono
      audioBuffer.length,
      audioBuffer.sampleRate,
    );

    const monoData = monoBuffer.getChannelData(0);

    // Average all channels
    for (let channel = 0; channel < audioBuffer.numberOfChannels; channel++) {
      const channelData = audioBuffer.getChannelData(channel);
      for (let i = 0; i < audioBuffer.length; i++) {
        monoData[i] += channelData[i] / audioBuffer.numberOfChannels;
      }
    }

    return monoBuffer;
  }

  /**
   * Encode AudioBuffer as WebM/Opus blob
   * Uses MediaRecorder API for native Opus encoding
   */
  async encodeAsWebM(audioBuffer, audioContext) {
    return new Promise((resolve, reject) => {
      // Create MediaStreamDestination
      const destination = audioContext.createMediaStreamDestination();

      // Create buffer source
      const source = audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(destination);

      // Create MediaRecorder with Opus codec
      const mediaRecorder = new MediaRecorder(destination.stream, {
        mimeType: "audio/webm;codecs=opus",
        audioBitsPerSecond: 16000, // 16kbps for voice
      });

      const chunks = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunks.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunks, { type: "audio/webm;codecs=opus" });
        resolve(blob);
      };

      mediaRecorder.onerror = (error) => {
        reject(error);
      };

      // Start recording and playback
      mediaRecorder.start();
      source.start();

      // Stop when source ends
      source.onended = () => {
        mediaRecorder.stop();
      };
    });
  }
}
