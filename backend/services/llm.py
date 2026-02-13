import fal_client
from core.config import get_settings
import asyncio
import json
from typing import AsyncGenerator, Dict, Any

settings = get_settings()

# Set FAL API key
import os
os.environ['FAL_KEY'] = settings.FAL_KEY

class LLMService:
    def __init__(self):
        self.model = "openrouter/router"
        self.llm_model = "google/gemini-2.5-flash"  # Stable model
        
        # Cached menu context (shared across all requests)
        self._cached_menu = None
        
        # Compact system prompt — optimized for low token count + fast LLM response
        self.system_prompt = "Sen GarsonAI. Türkçe, kısa, samimi, sadece düz JSON yanıt ver. Sadece spoken_response ve recommendation alanlarını doldur."
    
    def cache_menu(self, menu_context: str):
        """Cache menu context to avoid sending it repeatedly"""
        if self._cached_menu != menu_context:
            self._cached_menu = menu_context
            print(f"📋 LLM: Menu cached ({len(menu_context)} chars)")
        
    async def generate_stream(self, user_message: str, menu_context: str = "", start_time: float = None, conversation_history: list = None) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream LLM responses using fal.ai with OpenRouter
        Uses cached menu context to reduce prompt tokens
        """
        try:
            # Cache menu if provided
            if menu_context:
                self.cache_menu(menu_context)
            
            # Build conversation history string
            history_str = ""
            if conversation_history:
                turns = []
                for turn in conversation_history[-3:]:
                    turns.append(f"Müşteri: {turn['user']}\nGarson: {turn['assistant']}")
                history_str = "\n".join(turns) + "\n\n"
            
            # Build compact prompt
            if self._cached_menu:
                prompt = f"{self.system_prompt}\n\nMenü:\n{self._cached_menu}\n\n{history_str}Müşteri: {user_message}\n\nYanıt ver (JSON formatında):"
            else:
                prompt = f"{self.system_prompt}\n\n{history_str}Müşteri: {user_message}\n\nYanıt ver (JSON formatında):"
            
            print(f"🤖 LLM: Generating response for: {user_message}")
            print(f"📊 LLM: Prompt length: {len(prompt)} chars (~{len(prompt.split())} tokens)")
            
            # Use fal.stream for streaming
            full_response = ""
            has_content = False
            
            def sync_stream():
                return fal_client.stream(
                    self.model,
                    arguments={
                        "prompt": prompt,
                        "model": self.llm_model,
                        "temperature": 0.7,
                        "max_tokens": 200  # JSON response — enough for recommendation
                    }
                )
            
            # Non-blocking: create stream in thread, iterate with to_thread(next)
            _DONE = object()
            stream = await asyncio.to_thread(sync_stream)
            stream_iter = iter(stream)
            
            while True:
                event = await asyncio.to_thread(next, stream_iter, _DONE)
                if event is _DONE:
                    break
                
                if isinstance(event, dict):
                    # Check for 'output' field (full text so far)
                    if "output" in event and event["output"]:
                        chunk = event["output"]
                        
                        # Calculate the new content (delta)
                        new_content = chunk[len(full_response):] if chunk.startswith(full_response) else chunk
                        
                        if new_content:
                            full_response = chunk
                            has_content = True
                            
                            yield {
                                "type": "token",
                                "content": new_content,
                                "full_text": full_response
                            }
                    
                    # Check for 'partial' field
                    elif "partial" in event and event.get("partial"):
                        if "output" in event:
                            chunk = event["output"]
                            full_response = chunk
                            has_content = True
                            
                            yield {
                                "type": "token",
                                "content": chunk,
                                "full_text": full_response
                            }
            
            print(f"✅ LLM: Response complete: {full_response}")
            
            # If no content was streamed, fallback to non-streaming
            if not has_content:
                print("⚠️ LLM: No streaming content, trying subscribe...")
                result = await asyncio.to_thread(
                    fal_client.subscribe,
                    self.model,
                    arguments={
                        "prompt": prompt,
                        "model": self.llm_model,
                        "temperature": 0.7,
                        "max_tokens": 500
                    }
                )
                
                print(f"📊 LLM Subscribe result: {result}")
                
                if isinstance(result, dict) and "output" in result:
                    full_response = result["output"]
                    
                    yield {
                        "type": "token",
                        "content": full_response,
                        "full_text": full_response
                    }
            
            # Parse final structured response
            if full_response and full_response.strip():
                try:
                    # Strip markdown fences if present (```json ... ```)
                    clean = full_response.strip()
                    if clean.startswith("```"):
                        # Remove opening fence (```json or ```)
                        first_newline = clean.index("\n")
                        clean = clean[first_newline + 1:]
                    if clean.endswith("```"):
                        clean = clean[:-3]
                    clean = clean.strip()
                    
                    # Try to extract JSON from response
                    if "{" in clean and "}" in clean:
                        json_start = clean.index("{")
                        json_end = clean.rindex("}") + 1
                        json_str = clean[json_start:json_end]
                        structured = json.loads(json_str)
                    else:
                        # No JSON found, use full response as spoken text
                        structured = {
                            "spoken_response": full_response,
                            "intent": "info",
                            "product_name": None,
                            "quantity": 1
                        }
                        
                    yield {
                        "type": "complete",
                        "structured": structured
                    }
                    
                except Exception as parse_error:
                    print(f"⚠️ LLM: Could not parse JSON: {parse_error}")
                    yield {
                        "type": "complete",
                        "structured": {
                            "spoken_response": full_response,
                            "intent": "info",
                            "product_name": None,
                            "quantity": 1
                        }
                    }
            else:
                print("❌ LLM: Empty response!")
                yield {
                    "type": "complete",
                    "structured": {
                        "spoken_response": "Üzgünüm, anlayamadım. Tekrar söyler misiniz?",
                        "intent": "error",
                        "product_name": None,
                        "quantity": 1
                    }
                }
                
        except Exception as e:
            print(f"❌ LLM Error: {e}")
            import traceback
            traceback.print_exc()
            yield {
                "type": "complete",
                "structured": {
                    "spoken_response": "Üzgünüm, bir hata oluştu.",
                    "intent": "error",
                    "product_name": None,
                    "quantity": 1
                }
            }
