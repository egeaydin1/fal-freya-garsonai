import fal_client
from openai import OpenAI
from core.config import get_settings
import asyncio
import json
from typing import AsyncGenerator, Dict, Any

settings = get_settings()

import os
os.environ['FAL_KEY'] = settings.FAL_KEY

# Pre-warmed OpenAI client (persistent connection - OPT-7)
_openai_client = OpenAI(
    api_key="fal",
    base_url="https://fal.run/openrouter/router/openai/v1",
    default_headers={
        "Authorization": f"Key {settings.FAL_KEY}"
    }
)


class LLMService:
    def __init__(self):
        self.client = _openai_client
        self.llm_model = "google/gemini-2.5-flash" #meta-llama/llama-4-scout
        self._cached_menu = None

        self.system_prompt = """Sen GarsonAI, bir Türk restoranının sesli asistanısın. Türkçe, samimi ve doğal konuş. Kısa yanıt ver (max 2 cümle).

ÖNEMLİ: Her zaman ve SADECE aşağıdaki JSON formatında yanıt ver. JSON dışında hiçbir metin yazma.
{"spoken_response":"müşteriye sesli söylenecek yanıt","intent":"add|info|hi|recommend","product_name":"ürün adı","product_id":null,"quantity":1,"recommendation":{"product_id":1,"product_name":"ürün","reason":"öneri sebebi"}}

🔴 KRİTİK KURAL - spoken_response'un İLK CÜMLESİ:
spoken_response'u her zaman aşağıdaki başlangıç cümlelerinden BİRİYLE başlat. Bu cümleler önceden seslendirilmiş ve cache'leniyor, aynen yazılmalı:
- Sipariş eklerken → "Tabii, hemen sepetinize ekliyorum!" ile başla, sonra detayı ekle.
- Öneri yaparken → "Tabii ki, hemen önerebileceğim güzel seçenekler var." ile başla.
- Bilgi verirken → "Anladım, bir bakayım sizin için." ile başla.
- Menüye bakarken → "Bir dakika lütfen, menüye bakıyorum." veya "Bakalım sizin için neler var." ile başla.
- Onay verirken → "Güzel bir seçim! Hemen ekliyorum." ile başla.
- Genel kabul → "Peki, hemen halledelim!" ile başla.
- Selamlama → "Hoş geldiniz! Size nasıl yardımcı olabilirim?" ile başla.
Bu başlangıç cümlesinden sonra asıl içeriği ekle. Başlangıç cümlesi AYNEN yazılmalı, değiştirilmemeli.

Intent Kuralları:
- intent="hi": Karşılama mesajı.
- intent="add": Sipariş ekleme. product_name, product_id ve quantity doldur. Menüden doğru ürünü bul.
- intent="info": Bilgi verme. Menüdeki ürün bilgisini (açıklama, fiyat, alerjen) spoken_response'ta açıkla.
- intent="recommend": Öneri yapma. recommendation alanını MUTLAKA doldur. product_id menüdeki gerçek ID'yi kullan.

Öneri Kuralları:
- Müşteri "ne önerirsin", "tavsiye et", "ne yesem", "açım", "güzel bir şey" gibi derse → intent="recommend"
- Tatlı isterse tatlı kategorisinden, içecek isterse içecek kategorisinden öner.
- recommendation.product_id MENÜDE BULUNAN GERÇEK bir ID olmalı. Uydurma!
- recommendation.reason kısa ve ikna edici ol: "Bugünün en çok tercih edilen yemeği" gibi.
- spoken_response'ta ürünü tanıt ve neden önerdiğini anlat.

Genel Kurallar:
- Samimi ol ama profesyonel kal.
- Fiyatları söylerken "TL" yerine "lira" de.
- Alerjen sorularına duyarlı ol, menüdeki alerjen bilgisini kullan.
- Menüde olmayan bir ürün istenirse, kibarca menüdeki alternatifleri öner."""

    def cache_menu(self, menu_context: str):
        if self._cached_menu != menu_context:
            self._cached_menu = menu_context
            print(f"📋 LLM: Menu cached ({len(menu_context)} chars)")

    async def generate_stream(
        self, user_message: str, menu_context: str = "", start_time: float = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream LLM via OpenAI-compatible endpoint (OPT-2) for lower TTFT."""
        try:
            if menu_context:
                self.cache_menu(menu_context)

            messages = [
                {"role": "system", "content": self.system_prompt},
            ]
            if self._cached_menu:
                messages.append({
                    "role": "system",
                    "content": f"Menü:\n{self._cached_menu}"
                })
            messages.append({"role": "user", "content": user_message})

            print(f"🤖 LLM: Generating for: {user_message}")

            # OPT-2: OpenAI streaming for first token at ~600ms vs 1600ms
            def _stream():
                return self.client.chat.completions.create(
                    model=self.llm_model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=200,
                    stream=True,
                )

            stream = await asyncio.to_thread(_stream)

            full_response = ""
            has_content = False

            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    token = delta.content
                    full_response += token
                    has_content = True
                    yield {
                        "type": "token",
                        "content": token,
                        "full_text": full_response,
                    }

            print(f"✅ LLM complete: {full_response[:120]}")

            # Fallback: non-streaming if empty
            if not has_content:
                print("⚠️ LLM: No stream content, fallback subscribe...")
                result = await asyncio.to_thread(
                    fal_client.subscribe,
                    "openrouter/router",
                    arguments={
                        "prompt": f"{self.system_prompt}\nMenü:\n{self._cached_menu or ''}\nMüşteri: {user_message}\nJSON:",
                        "model": self.llm_model,
                        "temperature": 0.7,
                        "max_tokens": 200,
                    },
                )
                if isinstance(result, dict) and "output" in result:
                    full_response = result["output"]
                    yield {"type": "token", "content": full_response, "full_text": full_response}

            # Parse structured response
            structured = self._parse_response(full_response)
            yield {"type": "complete", "structured": structured}

        except Exception as e:
            print(f"❌ LLM Error: {e}")
            import traceback; traceback.print_exc()
            yield {
                "type": "complete",
                "structured": {
                    "spoken_response": "Üzgünüm, bir hata oluştu.",
                    "intent": "error",
                    "product_name": None,
                    "product_id": None,
                    "quantity": 1,
                },
            }

    def _parse_response(self, text: str) -> dict:
        """Extract JSON from LLM response text."""
        default = {
            "spoken_response": text,
            "intent": "info",
            "product_name": None,
            "product_id": None,
            "quantity": 1,
        }
        if not text or not text.strip():
            default["spoken_response"] = "Üzgünüm, anlayamadım. Tekrar söyler misiniz?"
            default["intent"] = "error"
            return default

        try:
            if "{" in text and "}" in text:
                json_str = text[text.index("{"):text.rindex("}") + 1]
                return json.loads(json_str)
            return default
        except Exception as e:
            print(f"⚠️ LLM parse error: {e}")
            return default
