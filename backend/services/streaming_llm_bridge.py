"""
Streaming LLM Bridge for Full-Duplex Voice Pipeline
Bridges incremental STT → streaming LLM → parallel TTS
Handles early triggering, sentence boundary detection, and async task orchestration
"""

import asyncio
import re
import time
from typing import AsyncGenerator, Dict, Any, Optional, Callable
from services.llm import LLMService
from services.tts import TTSService


class StreamingLLMBridge:
    """
    Orchestrates incremental LLM generation with parallel TTS spawning
    Detects first semantic sentence boundary and triggers TTS immediately
    """
    
    def __init__(self, llm_service: LLMService, tts_service: TTSService):
        self.llm = llm_service
        self.tts = tts_service
        self.active_tasks: Dict[str, asyncio.Task] = {}  # For barge-in cancellation
        
    async def process_stream(
        self,
        transcript: str,
        menu_context: str,
        start_time: float,
        websocket_send_json: Callable,
        websocket_send_bytes: Callable,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Process LLM stream with early TTS triggering
        
        Args:
            transcript: User's complete/partial transcript
            menu_context: Restaurant menu for LLM context
            start_time: Request start timestamp (for latency logging)
            websocket_send_json: WebSocket JSON send callback
            websocket_send_bytes: WebSocket binary send callback
            session_id: Voice session ID (for task tracking)
            
        Returns:
            dict: Structured LLM response data
        """
        full_response = ""
        structured_data = None
        first_token_logged = False
        first_sentence_complete = False
        tts_task = None
        first_sentence = ""
        
        print(f"🧠 LLM Bridge: Starting stream for transcript: {transcript[:100]}...")
        
        # Stream LLM tokens
        async for llm_event in self.llm.generate_stream(transcript, menu_context, start_time):
            if llm_event["type"] == "token":
                # Log first token latency
                if not first_token_logged:
                    elapsed = time.time() - start_time
                    print(f"[LLM first token]: {elapsed:06.3f}s")
                    first_token_logged = True
                
                # Send token to client
                await websocket_send_json({
                    "type": "ai_token",
                    "token": llm_event["content"],
                    "full_text": llm_event["full_text"]
                })
                full_response = llm_event["full_text"]
                
                # Detect first sentence boundary and trigger parallel TTS
                if not first_sentence_complete:
                    first_sentence_complete, first_sentence = self._detect_sentence_boundary(full_response)
                    
                    if first_sentence_complete and first_sentence:
                        print(f"⚡ Sentence boundary detected: '{first_sentence[:50]}...'")
                        
                        # Extract spoken response from JSON if present
                        spoken_text = self._extract_spoken_response(first_sentence, full_response)
                        
                        if spoken_text:
                            print(f"⚡ Parallel TTS: Starting for: '{spoken_text[:50]}...'")
                            
                            # Signal TTS start to client
                            await websocket_send_json({"type": "tts_start"})
                            
                            # Create parallel TTS task
                            tts_task = asyncio.create_task(
                                self._stream_tts_parallel(
                                    spoken_text, 
                                    start_time,
                                    websocket_send_bytes
                                )
                            )
                            self.active_tasks[f"{session_id}_tts"] = tts_task
            
            elif llm_event["type"] == "complete":
                structured_data = llm_event["structured"]
                elapsed = time.time() - start_time
                print(f"[LLM complete]: {elapsed:06.3f}s")
                print(f"🎯 Structured data: {structured_data}")
                
                await websocket_send_json({
                    "type": "ai_complete",
                    "data": structured_data
                })
        
        # Wait for parallel TTS or trigger fallback TTS
        if tts_task:
            print("⏳ Waiting for parallel TTS to complete...")
            await tts_task
            # Remove from active tasks
            self.active_tasks.pop(f"{session_id}_tts", None)
            
            await websocket_send_json({"type": "tts_complete"})
            elapsed = time.time() - start_time
            print(f"[COMPLETE] Total pipeline (parallel TTS): {elapsed:06.3f}s")
        else:
            # Fallback: No parallel TTS triggered, do full TTS now
            await self._fallback_tts(
                structured_data,
                start_time,
                websocket_send_json,
                websocket_send_bytes
            )
        
        return structured_data
    
    def _detect_sentence_boundary(self, text: str) -> tuple[bool, str]:
        """
        Detect first complete sentence in text
        Returns: (sentence_complete: bool, first_sentence: str)
        """
        if not text:
            return False, ""
        
        # Look for sentence-ending punctuation (. ! ?)
        match = re.search(r'[.!?]\s*', text)
        if match:
            first_sentence = text[:match.end()].strip()
            return True, first_sentence
        
        return False, ""
    
    def _extract_spoken_response(self, first_sentence: str, full_text: str) -> Optional[str]:
        """
        Extract spoken response from JSON if present
        Falls back to raw text if no JSON structure
        """
        # Check if response contains JSON structure
        if '"spoken_response"' in full_text:
            try:
                # Try to extract from JSON
                spoken_match = re.search(r'"spoken_response"\s*:\s*"([^"]+)"', full_text)
                if spoken_match:
                    spoken_text = spoken_match.group(1)
                    # Check if first sentence is complete
                    if re.search(r'[.!?]\s*$', spoken_text):
                        return spoken_text
                    # If not complete, wait for more tokens
                    return None
            except Exception as e:
                print(f"⚠️ JSON extraction error: {e}")
        
        # Fallback: use first_sentence raw
        return first_sentence
    
    async def _stream_tts_parallel(
        self,
        text: str,
        start_time: float,
        websocket_send_bytes: Callable
    ):
        """
        Stream TTS audio chunks in parallel with LLM generation
        """
        chunk_count = 0
        try:
            async for audio_chunk in self.tts.speak_stream(text, start_time):
                if audio_chunk:
                    if chunk_count == 0:
                        elapsed = time.time() - start_time
                        print(f"[Audio playback start]: {elapsed:06.3f}s (parallel TTS first chunk)")
                    chunk_count += 1
                    await websocket_send_bytes(audio_chunk)
            
            print(f"✅ Parallel TTS complete: {chunk_count} chunks sent")
        except asyncio.CancelledError:
            print(f"⚠️ Parallel TTS cancelled (barge-in)")
            raise
        except Exception as e:
            print(f"❌ Parallel TTS error: {e}")
            raise
    
    async def _fallback_tts(
        self,
        structured_data: Optional[Dict[str, Any]],
        start_time: float,
        websocket_send_json: Callable,
        websocket_send_bytes: Callable
    ):
        """
        Fallback TTS when parallel TTS wasn't triggered
        (e.g., no sentence boundary detected during LLM stream)
        """
        print(f"🔍 Fallback TTS: structured_data={structured_data}")
        
        if structured_data and "spoken_response" in structured_data:
            spoken_text = structured_data["spoken_response"]
            print(f"🗣️ TTS: Will synthesize: {spoken_text}")
            
            if spoken_text and spoken_text.strip():
                await websocket_send_json({"type": "tts_start"})
                
                chunk_count = 0
                async for audio_chunk in self.tts.speak_stream(spoken_text, start_time):
                    if audio_chunk:
                        if chunk_count == 0:
                            elapsed = time.time() - start_time
                            print(f"[Audio playback start]: {elapsed:06.3f}s (fallback TTS)")
                        chunk_count += 1
                        await websocket_send_bytes(audio_chunk)
                
                await websocket_send_json({"type": "tts_complete"})
                elapsed = time.time() - start_time
                print(f"[COMPLETE] Total pipeline (fallback TTS): {elapsed:06.3f}s")
            else:
                print("⚠️ No spoken_response to synthesize")
        else:
            print(f"❌ No structured_data or spoken_response. Data: {structured_data}")
    
    async def cancel_active_streams(self, session_id: str):
        """
        Cancel all active LLM/TTS tasks for a session (for barge-in)
        """
        task_key = f"{session_id}_tts"
        if task_key in self.active_tasks:
            task = self.active_tasks[task_key]
            if not task.done():
                print(f"🛑 Cancelling active TTS for session {session_id}")
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            del self.active_tasks[task_key]
            print(f"✅ Session {session_id} streams cancelled")


# Singleton instance
_bridge_instance: Optional[StreamingLLMBridge] = None

def get_llm_bridge() -> StreamingLLMBridge:
    """Get or create StreamingLLMBridge singleton"""
    global _bridge_instance
    if _bridge_instance is None:
        from services import LLMService, TTSService
        _bridge_instance = StreamingLLMBridge(
            llm_service=LLMService(),
            tts_service=TTSService()
        )
    return _bridge_instance
