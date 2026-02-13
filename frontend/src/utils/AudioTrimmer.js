/**
 * Audio Trimmer - Smart Silence Detection & Removal
 *
 * Removes silence from beginning and end of audio to reduce payload size
 * and improve STT accuracy by removing unnecessary audio.
 *
 * Optimization: 300-500ms of silence typically removed = smaller payload
 */
export class AudioTrimmer {
  constructor(options = {}) {
    this.silenceThreshold = options.silenceThreshold || 0.01; // RMS threshold
    this.targetSampleRate = options.targetSampleRate || 16000;
  }

  /**
   * Trim silence from audio blob
   * Returns trimmed audio blob
   */
  async trimSilence(audioBlob) {
    try {
      console.log(
        `🔧 Trimmer: Original size: ${(audioBlob.size / 1024).toFixed(2)}KB`,
      );

      // Create audio context
      const audioContext = new (
        window.AudioContext || window.webkitAudioContext
      )({
        sampleRate: this.targetSampleRate,
      });

      // Decode audio
      const arrayBuffer = await audioBlob.arrayBuffer();
      const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);

      // Get audio data from first channel
      const channelData = audioBuffer.getChannelData(0);

      // Find start and end indices (non-silent regions)
      const { startIndex, endIndex } = this._findNonSilentRegion(channelData);

      // If no change needed, return original
      if (startIndex === 0 && endIndex === channelData.length - 1) {
        console.log("✅ Trimmer: No silence to trim");
        await audioContext.close();
        return audioBlob;
      }

      // Create new buffer with trimmed audio
      const trimmedLength = endIndex - startIndex + 1;
      const trimmedBuffer = audioContext.createBuffer(
        audioBuffer.numberOfChannels,
        trimmedLength,
        audioBuffer.sampleRate,
      );

      // Copy trimmed data
      for (let channel = 0; channel < audioBuffer.numberOfChannels; channel++) {
        const originalData = audioBuffer.getChannelData(channel);
        const trimmedData = trimmedBuffer.getChannelData(channel);

        for (let i = 0; i < trimmedLength; i++) {
          trimmedData[i] = originalData[startIndex + i];
        }
      }

      // Encode back to blob
      const trimmedBlob = await this._encodeToBlob(trimmedBuffer, audioContext);

      const savedMs =
        ((channelData.length - trimmedLength) / this.targetSampleRate) * 1000;
      console.log(
        `✅ Trimmer: Trimmed ${savedMs.toFixed(0)}ms silence (${(trimmedBlob.size / 1024).toFixed(2)}KB)`,
      );

      await audioContext.close();
      return trimmedBlob;
    } catch (error) {
      console.error("⚠️ Trimmer error, using original:", error);
      return audioBlob;
    }
  }

  /**
   * Find non-silent region using RMS threshold
   * Returns { startIndex, endIndex }
   */
  _findNonSilentRegion(channelData) {
    const windowSize = 160; // 10ms window at 16kHz
    let startIndex = 0;
    let endIndex = channelData.length - 1;

    // Find start (skip leading silence)
    for (let i = 0; i < channelData.length - windowSize; i += windowSize) {
      const rms = this._calculateRMS(channelData, i, i + windowSize);
      if (rms > this.silenceThreshold) {
        startIndex = Math.max(0, i - windowSize); // Keep 1 window before
        break;
      }
    }

    // Find end (skip trailing silence)
    for (
      let i = channelData.length - windowSize;
      i > startIndex;
      i -= windowSize
    ) {
      const rms = this._calculateRMS(channelData, i, i + windowSize);
      if (rms > this.silenceThreshold) {
        endIndex = Math.min(channelData.length - 1, i + windowSize * 2); // Keep 2 windows after
        break;
      }
    }

    return { startIndex, endIndex };
  }

  /**
   * Calculate RMS (Root Mean Square) of audio segment
   */
  _calculateRMS(data, start, end) {
    let sum = 0;
    const length = end - start;

    for (let i = start; i < end && i < data.length; i++) {
      sum += data[i] * data[i];
    }

    return Math.sqrt(sum / length);
  }

  /**
   * Encode AudioBuffer to WebM blob
   */
  async _encodeToBlob(audioBuffer, audioContext) {
    return new Promise((resolve, reject) => {
      const destination = audioContext.createMediaStreamDestination();
      const source = audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(destination);

      const mediaRecorder = new MediaRecorder(destination.stream, {
        mimeType: "audio/webm;codecs=opus",
        audioBitsPerSecond: 16000,
      });

      const chunks = [];
      mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
      mediaRecorder.onstop = () =>
        resolve(new Blob(chunks, { type: "audio/webm" }));
      mediaRecorder.onerror = reject;

      mediaRecorder.start();
      source.start();
      source.onended = () => {
        setTimeout(() => mediaRecorder.stop(), 100);
      };
    });
  }
}
