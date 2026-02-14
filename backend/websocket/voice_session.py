"""
Voice Session State Machine for Full-Duplex Streaming
Manages incremental STT, early LLM triggering, parallel TTS, and barge-in.
"""

import asyncio
from typing import Literal, Optional
from dataclasses import dataclass, field
from datetime import datetime
import time


SessionState = Literal[
    "IDLE",
    "LISTENING", 
    "PROCESSING_STT",
    "GENERATING_LLM",
    "STREAMING_TTS",
    "INTERRUPTED"
]


@dataclass
class VoiceSession:
    """
    Full-duplex voice session with state management.
    
    Features:
    - Incremental STT (process while user speaks)
    - Early LLM triggering (semantic boundaries)
    - Parallel TTS streaming
    - Barge-in support (interrupt AI)
    """
    
    session_id: str
    table_id: str
    start_time: float = field(default_factory=time.time)
    
    # State management
    state: SessionState = "IDLE"
    
    # Audio buffering
    audio_buffer: bytearray = field(default_factory=bytearray)
    last_chunk_time: float = field(default_factory=time.time)
    
    # Transcription
    partial_transcript: str = ""
    full_transcript: str = ""
    last_partial_stt_time: float = 0
    chunk_count: int = 0  # Track number of 500ms chunks received
    
    # LLM streaming
    llm_stream_task: Optional[asyncio.Task] = None
    llm_full_response: str = ""
    llm_first_sentence: str = ""
    
    # TTS streaming
    tts_stream_task: Optional[asyncio.Task] = None
    tts_started: bool = False
    
    # Timing metrics
    stt_start_time: float = 0
    llm_start_time: float = 0
    tts_start_time: float = 0
    first_audio_time: float = 0
    
    # Configuration — tuned for sub-2s latency
    MIN_CHUNKS_FOR_PARTIAL: int = 2  # 2 x 250ms = 500ms min audio for partial STT
    MIN_STT_INTERVAL: float = 0.6    # Minimum 600ms between partial STT calls
    SILENCE_THRESHOLD: float = 0.3   # 300ms silence triggers early LLM
    MAX_BUFFER_SIZE: int = 1024 * 1024  # 1MB max buffer
    
    def can_process_partial_stt(self) -> bool:
        """Check if enough audio accumulated for partial STT.
        Uses chunk count (not byte size) since audio is compressed Opus."""
        time_since_last = time.time() - self.last_partial_stt_time
        
        return (
            self.chunk_count >= self.MIN_CHUNKS_FOR_PARTIAL and
            time_since_last >= self.MIN_STT_INTERVAL
        )
    
    def should_trigger_llm(self) -> bool:
        """
        Determine if LLM should start early.
        
        Triggers on:
        - Semantic pause (ends with punctuation)
        - High-confidence partial result
        - Silence detection
        """
        if not self.partial_transcript:
            return False
        
        # Semantic boundary detection
        if self.partial_transcript.strip().endswith((".", "!", "?")):
            return True
        
        # Minimum words threshold
        word_count = len(self.partial_transcript.split())
        if word_count >= 3:  # At least 3 words
            silence_duration = time.time() - self.last_chunk_time
            if silence_duration >= self.SILENCE_THRESHOLD:
                return True
        
        return False
    
    def get_first_sentence(self, text: str) -> Optional[str]:
        """Extract first complete sentence from streaming text."""
        import re
        match = re.search(r'^(.*?[.!?])\s*', text)
        if match:
            return match.group(1).strip()
        return None
    
    async def cancel_active_streams(self):
        """Cancel all active async tasks (for interruption)."""
        if self.llm_stream_task and not self.llm_stream_task.done():
            self.llm_stream_task.cancel()
            try:
                await self.llm_stream_task
            except asyncio.CancelledError:
                pass
        
        if self.tts_stream_task and not self.tts_stream_task.done():
            self.tts_stream_task.cancel()
            try:
                await self.tts_stream_task
            except asyncio.CancelledError:
                pass
        
        self.llm_stream_task = None
        self.tts_stream_task = None
    
    def reset_for_new_input(self):
        """Reset session for new user input (after interrupt)."""
        self.audio_buffer.clear()
        self.partial_transcript = ""
        self.full_transcript = ""
        self.llm_full_response = ""
        self.llm_first_sentence = ""
        self.tts_started = False
        self.chunk_count = 0
        self.state = "LISTENING"
    
    def add_audio_chunk(self, chunk: bytes):
        """Add audio chunk to buffer."""
        self.audio_buffer.extend(chunk)
        self.last_chunk_time = time.time()
        self.chunk_count += 1
        
        # Safety: prevent buffer overflow
        if len(self.audio_buffer) > self.MAX_BUFFER_SIZE:
            # Keep only last 500KB
            self.audio_buffer = bytearray(self.audio_buffer[-500000:])
    
    def get_audio_for_processing(self) -> bytes:
        """Get audio buffer for STT processing."""
        return bytes(self.audio_buffer)
    
    def clear_processed_audio(self, keep_overlap: bool = True):
        """
        Clear processed audio from buffer.
        
        Args:
            keep_overlap: Keep 500ms overlap for context continuity
        """
        if keep_overlap:
            # Keep last chunk for context continuity
            overlap_size = 8000  # ~500ms at 16kHz PCM, or ~1s of Opus
            if len(self.audio_buffer) > overlap_size:
                self.audio_buffer = bytearray(self.audio_buffer[-overlap_size:])
        else:
            self.audio_buffer.clear()
        
        self.chunk_count = 0
        self.last_partial_stt_time = time.time()
    
    def get_metrics(self) -> dict:
        """Get performance metrics for debugging."""
        current_time = time.time()
        
        return {
            "session_duration": current_time - self.start_time,
            "state": self.state,
            "buffer_size_kb": len(self.audio_buffer) / 1024,
            "buffer_duration_s": len(self.audio_buffer) / (16000 * 2),
            "partial_transcript_len": len(self.partial_transcript),
            "full_transcript_len": len(self.full_transcript),
            "llm_active": self.llm_stream_task is not None and not self.llm_stream_task.done(),
            "tts_active": self.tts_stream_task is not None and not self.tts_stream_task.done(),
            "time_to_first_audio": self.first_audio_time - self.start_time if self.first_audio_time else None,
        }
    
    def __repr__(self):
        return f"VoiceSession(state={self.state}, buffer={len(self.audio_buffer)}B, transcript='{self.partial_transcript[:30]}...')"


class SessionManager:
    """Manages multiple voice sessions (one per WebSocket connection)."""
    
    def __init__(self):
        self._sessions: dict[str, VoiceSession] = {}
    
    def create_session(self, session_id: str, table_id: str) -> VoiceSession:
        """Create new voice session."""
        session = VoiceSession(session_id=session_id, table_id=table_id)
        self._sessions[session_id] = session
        print(f"📱 Session created: {session_id} for table {table_id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[VoiceSession]:
        """Get existing session."""
        return self._sessions.get(session_id)
    
    async def remove_session(self, session_id: str):
        """Remove and cleanup session."""
        session = self._sessions.get(session_id)
        if session:
            await session.cancel_active_streams()
            del self._sessions[session_id]
            print(f"🗑️ Session removed: {session_id}")
    
    def get_active_count(self) -> int:
        """Get count of active sessions."""
        return len(self._sessions)


# Global session manager instance
session_manager = SessionManager()
