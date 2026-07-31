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
        
        # Ultra-compact system prompt (~25 tokens)
        self.system_prompt = """GarsonAI bot. Kısa yanıt (max 10 kelime).
JSON only: {"spoken_response":"...","intent":"add|info|hi","product_name":"...","quantity":1}"""
    
    def cache_menu(self, menu_context: str):
        """Cache menu context to avoid sending it repeatedly"""
        if self._cached_menu != menu_context:
            self._cached_menu = menu_context
            print(f"📋 LLM: Menu cached ({len(menu_context)} chars)")
        
    async def generate_stream(self, user_message: str, menu_context: str = "", start_time: float = None) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream LLM responses using fal.ai with OpenRouter
        Uses cached menu context to reduce prompt tokens
        """
        try:
            # Cache menu if provided
            if menu_context:
                self.cache_menu(menu_context)
            
            # Build compact prompt (menu reference cached on OpenRouter side)
            # Note: OpenRouter supports prompt caching via prompt_prefix
            if self._cached_menu:
                # Use cached menu reference
                prompt = f"{self.system_prompt}\n\nMenü:\n{self._cached_menu}\n\nMüşteri: {user_message}\n\nYanıt ver (JSON formatında):"
            else:
                # No menu available
                prompt = f"{self.system_prompt}\n\nMüşteri: {user_message}\n\nYanıt ver (JSON formatında):"
            
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
                        "max_tokens": 100  # Voice AI needs short responses
                    }
                )
            
            stream = await asyncio.to_thread(sync_stream)
            
            for event in stream:
                print(f"📨 LLM Event: {event}")
                
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
                    # Try to extract JSON from response
                    if "{" in full_response and "}" in full_response:
                        json_start = full_response.index("{")
                        json_end = full_response.rindex("}") + 1
                        json_str = full_response[json_start:json_end]
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
