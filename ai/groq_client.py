"""
Groq API client for AI fallback operations.
Uses Llama 3.1 8B for fast inference.
"""
import os
import json
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')


class GroqClient:
    """
    Groq API client for AI-powered parsing fallback.
    
    Features:
    - City name normalization (case correction)
    - City-region validation
    - Message parsing when regex fails
    - Russian -> Ukrainian translation
    """
    
    API_URL = "https://api.groq.com/openai/v1/chat/completions"
    MODEL = "llama-3.1-8b-instant"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or GROQ_API_KEY
        self._available = bool(self.api_key)
        self._call_count = 0
    
    @property
    def is_available(self) -> bool:
        return self._available
    
    def _call_api(self, prompt: str, max_tokens: int = 50) -> Optional[str]:
        """Make API call to Groq."""
        if not self._available:
            return None
        
        try:
            import requests
            
            self._call_count += 1
            
            response = requests.post(
                self.API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0
                },
                timeout=5
            )
            
            if not response.ok:
                logger.warning(f"Groq API error: {response.status_code}")
                return None
            
            data = response.json()
            return data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            
        except Exception as e:
            logger.warning(f"Groq API exception: {e}")
            return None
    
    def normalize_city(self, city: str) -> str:
        """
        Normalize city name to nominative case.
        
        Examples:
        - "Софіївки" -> "Софіївка"
        - "Кривого Рогу" -> "Кривий Ріг"
        """
        if not city or len(city) < 3:
            return city
        
        prompt = f"""Перетвори назву українського населеного пункту в називний відмінок.

Вхід: "{city}"

Правила:
- Якщо вже в називному - поверни без змін
- "Софіївки" -> "Софіївка"
- "Кривого Рогу" -> "Кривий Ріг"
- "Балаклію" -> "Балаклія"

Відповідай ТІЛЬКИ назвою в називному відмінку.
Відповідь:"""

        result = self._call_api(prompt, max_tokens=30)
        
        if result and len(result) <= len(city) + 5:
            logger.debug(f"Groq normalized: '{city}' -> '{result}'")
            return result[0].upper() + result[1:] if result else city
        
        return city
    
    def validate_city_region(self, city: str, region: str) -> tuple:
        """
        Validate if city belongs to region.
        Returns (city, correct_region).
        """
        if not city or not region:
            return city, region
        
        prompt = f"""Перевір чи "{city}" знаходиться в "{region}".

Якщо ТАК - відповідай: ПРАВИЛЬНО
Якщо НІ - відповідай назвою правильної області (формат: "Назва обл.")

Відповідь:"""

        result = self._call_api(prompt, max_tokens=30)
        
        if not result:
            return city, region
        
        if 'ПРАВИЛЬНО' in result.upper():
            return city, region
        
        if 'обл' in result.lower():
            correct_region = result.strip()
            if not correct_region.endswith('обл.'):
                correct_region = correct_region.replace('область', 'обл.').replace('обл', 'обл.')
            logger.info(f"Groq validated: {city} ({region}) -> ({correct_region})")
            return city, correct_region
        
        return city, region
    
    def get_region(self, city: str, hint: str = None) -> Optional[str]:
        """
        Get region for a city using AI.
        """
        context = f"місто/село: {city}"
        if hint:
            context += f", контекст: {hint}"
        
        prompt = f"""Визнач область України для населеного пункту.

{context}

Відповідай ТІЛЬКИ назвою області у форматі "Назва обл."
Якщо не знаєш - відповідай "невідомо"
Відповідь:"""

        result = self._call_api(prompt, max_tokens=30)
        
        if not result or 'невідомо' in result.lower():
            return None
        
        if not result.endswith('обл.'):
            result = result.replace('область', 'обл.').replace('обл', 'обл.')
        
        logger.debug(f"Groq region: {city} -> {result}")
        return result
    
    def parse_message(self, text: str) -> List[Dict[str, Any]]:
        """
        Parse message using AI when regex fails.
        
        Returns list of dicts: [{"city": "X", "region": "Y обл.", "type": "БПЛА"}, ...]
        """
        if not text or len(text) < 10:
            return []
        
        prompt = f"""Проаналізуй повідомлення про загрози і витягни міста.

Повідомлення:
"{text[:500]}"

Для кожного міста вкажи:
1. Назва (називний відмінок)
2. Область ("Назва обл.")
3. Тип: БПЛА, Ракета, КАБ або Вибухи

Жаргон: "балалайка", "мопед", "шахед" = БПЛА

Формат JSON: [{{"city": "Місто", "region": "Область обл.", "type": "БПЛА"}}]
Якщо міст немає: []

Відповідь:"""

        result = self._call_api(prompt, max_tokens=200)
        
        if not result:
            return []
        
        try:
            import re
            json_match = re.search(r'\[.*\]', result, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                if isinstance(parsed, list):
                    cleaned = []
                    for item in parsed:
                        if isinstance(item, dict) and 'city' in item:
                            city = item.get('city', '').strip()
                            region = item.get('region', '').strip()
                            threat_type = item.get('type', 'БПЛА').strip()
                            if city and region:
                                if not region.endswith('обл.'):
                                    region = region.replace('область', 'обл.')
                                cleaned.append({
                                    'city': city,
                                    'region': region,
                                    'type': threat_type
                                })
                    if cleaned:
                        logger.info(f"Groq parsed: {cleaned}")
                    return cleaned
        except json.JSONDecodeError:
            pass
        
        return []
    
    def translate_russian(self, city_ru: str) -> str:
        """
        Translate Russian city name to Ukrainian.
        """
        # Quick lookup for common names
        ru_to_ua = {
            'кривой рог': 'Кривий Ріг',
            'днепр': 'Дніпро',
            'николаев': 'Миколаїв',
            'харьков': 'Харків',
            'киев': 'Київ',
            'одесса': 'Одеса',
            'запорожье': 'Запоріжжя',
            'чернигов': 'Чернігів',
            'черноморск': 'Чорноморськ',
        }
        
        if city_ru.lower() in ru_to_ua:
            return ru_to_ua[city_ru.lower()]
        
        # Check for Russian-specific chars
        if not any(c in city_ru for c in 'ыэъёЫЭЪЁ'):
            return city_ru
        
        prompt = f"""Перекладі російську назву міста на українську.

"{city_ru}"

Відповідай ТІЛЬКИ українською назвою.
Відповідь:"""

        result = self._call_api(prompt, max_tokens=30)
        
        if result and len(result) <= len(city_ru) + 10:
            logger.debug(f"Groq translated: '{city_ru}' -> '{result}'")
            return result
        
        return city_ru
    
    @property
    def call_count(self) -> int:
        return self._call_count


# Global client instance
_client: Optional[GroqClient] = None


def get_client() -> GroqClient:
    """Get or create Groq client instance."""
    global _client
    if _client is None:
        _client = GroqClient()
    return _client
