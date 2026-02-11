import fal_client
from core.config import get_settings
import asyncio
import json
from typing import AsyncGenerator, Dict, Any

settings = get_settings()

class LLMService:
    def __init__(self):
        self.model = "openrouter/router"
        self.system_prompt = """Sen GarsonAI'sın, profesyonel bir Türk restoranı garsonusun.

Kurallar:
- Kısa ve net cümleler kur
- Emoji kullanma
- Doğal garson tonu kullan
- Ürün öner
- Siparişleri onayla
- Müşterinin niyetini anla

Her yanıt JSON formatında şu bilgileri içermeli (ama sadece konuş):
{
  "spoken_response": "...",
  "intent": "add_to_cart | remove_item | checkout | info | greeting",
  "product_name": "...",
  "quantity": 2
}"""
        
    async def generate_stream(self, user_message: str, menu_context: str = "") -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream LLM responses using Gemini 2.5 Flash via OpenRouter
        Yields progressive tokens and structured data
        """
        try:
            prompt = f"{self.system_prompt}\n\nMenü:\n{menu_context}\n\nMüşteri: {user_message}\n\nYanıt ver:"
            
            # Use fal streaming
            stream = fal_client.stream(
                self.model,
                arguments={
                    "model": "google/gemini-2.5-flash",
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "stream": True
                }
            )
            
            full_response = ""
            
            for event in stream:
                if hasattr(event, 'choices') and len(event.choices) > 0:
                    delta = event.choices[0].delta
                    if hasattr(delta, 'content') and delta.content:
                        chunk = delta.content
                        full_response += chunk
                        
                        yield {
                            "type": "token",
                            "content": chunk,
                            "full_text": full_response
                        }
            
            # Parse final structured response
            try:
                # Try to extract JSON from response
                if "{" in full_response and "}" in full_response:
                    json_start = full_response.index("{")
                    json_end = full_response.rindex("}") + 1
                    json_str = full_response[json_start:json_end]
                    structured = json.loads(json_str)
                else:
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
                
            except:
                yield {
                    "type": "complete",
                    "structured": {
                        "spoken_response": full_response,
                        "intent": "info",
                        "product_name": None,
                        "quantity": 1
                    }
                }
                
        except Exception as e:
            print(f"LLM Error: {e}")
            yield {
                "type": "error",
                "error": str(e)
            }
