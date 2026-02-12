/**
 * Audio Trimmer - Removes silence from beginning and end of audio
 * This reduces audio duration → faster Whisper inference
 * 
 * Strategy:
 * - Calculate RMS (Root Mean Square) for each sample
 * - Detect first non-silent sample from start
 * - Detect last non-silent sample from end
 * - Return trimmed audio
 * 
 * Expected gain: ~30-40% faster inference for typical speech
 */
export class AudioTrimmer {
  constructor(options = {}) {
    this.silenceThreshold = options.silenceThreshold || 0.01; // RMS threshold
    this.silencePaddingMs = options.silencePaddingMs || 100; // Keep 100ms padding
  }

  /**
   * Trim silence from audio blob
   * @param {Blob} audioBlob - Original audio blob
   * @returns {Promise<Blob>} - Trimmed audio blob
   */
  async trimSilence(audioBlob) {
    try {
      console.log(`✂️ AudioTrimmer: Original size: ${audioBlob.size} bytes`);
      
      // Decode audio to get raw samples
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const arrayBuffer = await audioBlob.arrayBuffer();
      const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
      
      // Get channel data (mono or first channel if stereo)
      const channelData = audioBuffer.getChannelData(0);
      const sampleRate = audioBuffer.sampleRate;
      
      console.log(`📊 AudioTrimmer: ${channelData.length} samples at ${sampleRate}Hz`);
      
      // Find first non-silent sample
      const startIndex = this._findFirstNonSilence(channelData, sampleRate);
      
      // Find last non-silent sample
      const endIndex = this._findLastNonSilence(channelData, sampleRate);
      
      if (startIndex >= endIndex) {
        console.warn('⚠️ AudioTrimmer: Audio is entirely silent, returning original');
        return audioBlob;
      }
      
      // Calculate duration reduction
      const originalDuration = audioBuffer.duration;
      const trimmedDuration = (endIndex - startIndex) / sampleRate;
      const reductionPercent = ((originalDuration - trimmedDuration) / originalDuration * 100).toFixed(1);
      
      console.log(`✂️ AudioTrimmer: Trimmed ${reductionPercent}% (${originalDuration.toFixed(2)}s → ${trimmedDuration.toFixed(2)}s)`);
      
      // Create new AudioBuffer with trimmed data
      const trimmedLength = endIndex - startIndex;
      const trimmedBuffer = audioContext.createBuffer(
        audioBuffer.numberOfChannels,
        trimmedLength,
        sampleRate
      );
      
      // Copy trimmed data to new buffer
      for (let channel = 0; channel < audioBuffer.numberOfChannels; channel++) {
        const originalChannel = audioBuffer.getChannelData(channel);
        const trimmedChannel = trimmedBuffer.getChannelData(channel);
        
        for (let i = 0; i < trimmedLength; i++) {
          trimmedChannel[i] = originalChannel[startIndex + i];
        }
      }
      
      // Convert trimmed buffer back to blob
      const trimmedBlob = await this._audioBufferToBlob(trimmedBuffer);
      
      console.log(`✅ AudioTrimmer: Final size: ${trimmedBlob.size} bytes`);
      
      return trimmedBlob;
      
    } catch (error) {
      console.error('❌ AudioTrimmer: Error during trimming:', error);
      console.warn('⚠️ AudioTrimmer: Returning original audio');
      return audioBlob;
    }
  }

  /**
   * Find first non-silent sample index
   */
  _findFirstNonSilence(channelData, sampleRate) {
    const paddingSamples = Math.floor((this.silencePaddingMs / 1000) * sampleRate);
    
    for (let i = 0; i < channelData.length; i++) {
      if (Math.abs(channelData[i]) > this.silenceThreshold) {
        // Found first non-silent sample, go back by padding
        return Math.max(0, i - paddingSamples);
      }
    }
    
    return 0;
  }

  /**
   * Find last non-silent sample index
   */
  _findLastNonSilence(channelData, sampleRate) {
    const paddingSamples = Math.floor((this.silencePaddingMs / 1000) * sampleRate);
    
    for (let i = channelData.length - 1; i >= 0; i--) {
      if (Math.abs(channelData[i]) > this.silenceThreshold) {
        // Found last non-silent sample, add padding
        return Math.min(channelData.length, i + paddingSamples);
      }
    }
    
    return channelData.length;
  }

  /**
   * Convert AudioBuffer to Blob
   * Uses OfflineAudioContext to encode to WebM
   */
  async _audioBufferToBlob(audioBuffer) {
    // Create offline context for rendering
    const offlineContext = new OfflineAudioContext(
      audioBuffer.numberOfChannels,
      audioBuffer.length,
      audioBuffer.sampleRate
    );
    
    // Create buffer source
    const source = offlineContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(offlineContext.destination);
    source.start();
    
    // Render to get final buffer
    const renderedBuffer = await offlineContext.startRendering();
    
    // Convert to WAV (simpler than WebM encoding in browser)
    // Note: WAV is larger but encoding is instant
    const wavBlob = this._audioBufferToWav(renderedBuffer);
    
    return wavBlob;
  }

  /**
   * Convert AudioBuffer to WAV blob
   * Simple PCM WAV encoding
   */
  _audioBufferToWav(audioBuffer) {
    const numberOfChannels = audioBuffer.numberOfChannels;
    const sampleRate = audioBuffer.sampleRate;
    const length = audioBuffer.length * numberOfChannels * 2;
    
    const buffer = new ArrayBuffer(44 + length);
    const view = new DataView(buffer);
    
    // WAV header
    this._writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + length, true);
    this._writeString(view, 8, 'WAVE');
    this._writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true); // PCM
    view.setUint16(20, 1, true); // PCM format
    view.setUint16(22, numberOfChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * numberOfChannels * 2, true);
    view.setUint16(32, numberOfChannels * 2, true);
    view.setUint16(34, 16, true);
    this._writeString(view, 36, 'data');
    view.setUint32(40, length, true);
    
    // PCM samples
    let offset = 44;
    for (let i = 0; i < audioBuffer.length; i++) {
      for (let channel = 0; channel < numberOfChannels; channel++) {
        const sample = audioBuffer.getChannelData(channel)[i];
        const int16 = Math.max(-1, Math.min(1, sample)) * 0x7FFF;
        view.setInt16(offset, int16, true);
        offset += 2;
      }
    }
    
    return new Blob([buffer], { type: 'audio/wav' });
  }

  /**
   * Write string to DataView
   */
  _writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }
}
