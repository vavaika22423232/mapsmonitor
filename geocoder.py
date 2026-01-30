"""
OpenCage Geocoder with MAXIMUM economy mode + Groq AI fallback
- Single API call per unique city
- Persistent JSON cache
- Negative cache for not-found cities
- Returns oblast (region) name for Ukrainian cities
- Groq LLM as smart fallback when OpenCage fails
"""

import json
import os
import requests

OPENCAGE_API_KEY = os.environ.get('OPENCAGE_API_KEY', '')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')

# Use /data for persistent storage on Render, fallback to local dir
def _get_cache_path(filename):
    persistent_dir = os.environ.get('PERSISTENT_DATA_DIR', '/data')
    if os.path.isdir(persistent_dir):
        return os.path.join(persistent_dir, filename)
    return os.path.join(os.path.dirname(__file__), filename)

CACHE_FILE = _get_cache_path('geocode_cache.json')
NEGATIVE_CACHE_FILE = _get_cache_path('geocode_cache_negative.json')

# Global caches
_cache = {}  # city_key -> {'coords': (lat, lon), 'region': 'Область обл.'}
_negative_cache = set()  # city_keys that were not found

# Stats
_stats = {'hits': 0, 'misses': 0, 'api_calls': 0}


def _normalize_city_name(city: str) -> str:
    """Normalize Ukrainian city name from accusative/genitive to nominative case"""
    city_norm = city.strip()
    city_lower = city_norm.lower()
    
    # Specific known transformations (accusative/genitive -> nominative)
    known_transforms = {
        # Genitive (-и/-і) -> Nominative (-а/-я)
        'софіївки': 'Софіївка',
        'васильківки': 'Васильківка',
        'криничок': 'Кринички',
        'кринички': 'Кринички',
        'синельникового': 'Синельникове',
        'павлограда': 'Павлоград',
        'кривого рогу': 'Кривий Ріг',
        'середини-буди': 'Середина-Буда',
        'вільнянська': 'Вільнянськ',
        # Accusative (-у/-ю) -> Nominative
        'хотімлю': 'Хотімля',
        'балаклію': 'Балаклія',
        'вовчанську': 'Вовчанськ',
        'богодухову': 'Богодухів',
        'мену': 'Мена',
        'конотопу': 'Конотоп',
        'шостку': 'Шостка',
        'суму': 'Суми',
        'харкову': 'Харків',
        'києву': 'Київ',
        'одесу': 'Одеса',
        'полтаву': 'Полтава',
        'дніпру': 'Дніпро',
        'херсону': 'Херсон',
        'запоріжжю': 'Запоріжжя',
        'миколаєву': 'Миколаїв',
        'чернігову': 'Чернігів',
        'ізюму': 'Ізюм',
        'куп\'янську': 'Куп\'янськ',
        'павлограду': 'Павлоград',
        'кременчуку': 'Кременчук',
        'бахмуту': 'Бахмут',
        'покровську': 'Покровськ',
        'маріуполю': 'Маріуполь',
        'мелітополю': 'Мелітополь',
        'енергодару': 'Енергодар',
        'лозову': 'Лозова',
        'бровари': 'Бровари',
        'славутичу': 'Славутич',
        'долинської': 'Долинська',
        'долинську': 'Долинська',
        'саксагані': 'Саксагань',
        # Multi-word cities in accusative case
        'гнилицю першу': 'Гнилиця Перша',
        'велику димерку': 'Велика Димерка',
        'велику виску': 'Велика Виска',
        'стару салтівку': 'Стара Салтівка',
        'козачу лопань': 'Козача Лопань',
        'малу данилівку': 'Мала Данилівка',
        'нову водолагу': 'Нова Водолага',
        'стару водолагу': 'Стара Водолага',
        'середину-буду': 'Середина-Буда',
        'хутір-михайлівський': 'Хутір-Михайлівський',
        # Single-word accusative endings -у/-ю
        'грушуваху': 'Грушуваха',
        'комишуваху': 'Комишуваха',
        'оріль': 'Орілька',
        'орільку': 'Орілька',
        # More multi-word cities
        'велику бабку': 'Велика Бабка',
        'малу бабку': 'Мала Бабка',
        'стару бабку': 'Стара Бабка',
        'нову бабку': 'Нова Бабка',
        'велику писарівку': 'Велика Писарівка',
        'малу писарівку': 'Мала Писарівка',
        'велику кохнівку': 'Велика Кохнівка',
        'зеленому': 'Зелене',
        # Cities with -у/-ну endings
        'березну': 'Березна',
        'васильківку': 'Васильківка',
        'дмитрівку': 'Дмитрівка',
        'просяну': 'Просяна',
        'суданівку': 'Суданівка',
        'дослідне': 'Дослідне',
        'криничку': 'Кринички',
        'вільнянську': 'Вільнянськ',
    }
    
    if city_lower in known_transforms:
        return known_transforms[city_lower]
    
    # General rules for genitive -> nominative
    # -ки -> -ка (Софіївки -> Софіївка)
    if city_lower.endswith('ки') and len(city_lower) > 3:
        return city_norm[:-1] + 'а'
    
    # -ого -> -е (Синельникового -> Синельникове)  
    if city_lower.endswith('ого') and len(city_lower) > 4:
        return city_norm[:-3] + 'е'
    
    # General rules for accusative -> nominative
    # -лю -> -ля (Хотімлю -> Хотімля)
    if city_lower.endswith('лю') and len(city_lower) > 3:
        return city_norm[:-1] + 'я'
    
    return city_norm


def _normalize_key(city: str, region: str = None) -> str:
    """Create normalized cache key from city and region"""
    if not city:
        return ""
    
    # First normalize accusative case to nominative
    city_normalized = _normalize_city_name(city)
    
    # Then lowercase and clean
    city_norm = city_normalized.lower().strip()
    city_norm = city_norm.replace('\u02bc', "'").replace('ʼ', "'").replace("'", "'").replace('`', "'")
    city_norm = city_norm.replace('ё', 'е')  # normalize ё -> е
    
    # Normalize region - keep original form, just lowercase
    if region:
        region_norm = region.lower().strip()
        # Only remove "область" and "обл" words, keep regional suffix like "ська"
        region_norm = region_norm.replace(' область', '').replace(' обл.', '').replace(' обл', '')
        region_norm = region_norm.strip()
        if region_norm:
            return f"{city_norm}|{region_norm}"
    
    return city_norm


def _load_cache():
    """Load cache from disk"""
    global _cache, _negative_cache
    
    # Load positive cache
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for k, v in data.items():
                    if isinstance(v, dict):
                        _cache[k] = v
                    elif isinstance(v, list) and len(v) >= 2:
                        # Old format [lat, lon] - convert to new format
                        _cache[k] = {'coords': tuple(v), 'region': None}
                print(f"[GEOCODER] Cache loaded: {len(_cache)} cities", flush=True)
    except Exception as e:
        print(f"[GEOCODER] Error loading cache: {e}", flush=True)
        _cache = {}
    
    # Load negative cache
    try:
        if os.path.exists(NEGATIVE_CACHE_FILE):
            with open(NEGATIVE_CACHE_FILE, 'r', encoding='utf-8') as f:
                _negative_cache = set(json.load(f))
                print(f"[GEOCODER] Negative cache loaded: {len(_negative_cache)} entries", flush=True)
    except:
        _negative_cache = set()


def _save_cache():
    """Save positive cache to disk"""
    try:
        data = {}
        for k, v in _cache.items():
            if isinstance(v, dict):
                # Convert tuple coords to list for JSON
                data[k] = {
                    'coords': list(v.get('coords', [])) if v.get('coords') else None,
                    'region': v.get('region')
                }
            else:
                data[k] = v
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[GEOCODER] Error saving cache: {e}", flush=True)


def _save_negative_cache():
    """Save negative cache to disk"""
    try:
        with open(NEGATIVE_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(_negative_cache), f, ensure_ascii=False)
    except:
        pass


# Bounding boxes for oblasts (for validation)
PRIORITY_OBLAST_BOUNDS = {
    'харківська': (48.5, 50.5, 34.5, 38.5),
    'донецька': (47.0, 49.5, 36.5, 39.5),
    'луганська': (48.0, 50.0, 37.5, 40.5),
    'запорізька': (46.5, 48.5, 34.0, 37.5),
    'херсонська': (45.5, 47.5, 32.0, 35.5),
    'дніпропетровська': (47.5, 49.5, 33.5, 36.5),
    'миколаївська': (46.0, 48.5, 30.5, 33.5),
    'одеська': (45.0, 48.5, 28.5, 33.5),
    'полтавська': (48.5, 50.5, 32.0, 35.5),
    'сумська': (50.0, 52.5, 32.5, 35.5),
    'чернігівська': (50.5, 52.5, 30.5, 33.5),
    'київська': (49.0, 51.5, 29.0, 32.5),
    'черкаська': (48.5, 50.0, 30.5, 33.0),
    'кіровоградська': (47.5, 49.5, 30.5, 33.5),
    'житомирська': (49.5, 51.5, 27.5, 31.5),
    'вінницька': (48.0, 50.0, 27.5, 30.5),
    'хмельницька': (48.5, 50.5, 25.5, 28.5),
    'рівненська': (50.0, 52.0, 25.0, 27.5),
    'волинська': (50.5, 52.0, 23.5, 26.0),
    'львівська': (49.0, 50.5, 22.5, 25.0),
    'тернопільська': (48.5, 50.0, 24.5, 26.5),
    'івано-франківська': (48.0, 49.5, 23.5, 25.5),
    'закарпатська': (47.5, 49.0, 22.0, 24.5),
}


def _coords_in_oblast(lat: float, lng: float, region: str) -> bool:
    """Check if coordinates fall within oblast bounds"""
    if not region:
        return True
    region_lower = region.lower().strip()
    for oblast_key, bounds in PRIORITY_OBLAST_BOUNDS.items():
        if oblast_key in region_lower:
            lat_min, lat_max, lng_min, lng_max = bounds
            return lat_min <= lat <= lat_max and lng_min <= lng <= lng_max
    return True


def _format_region(region_raw: str) -> str:
    """Format region name to standard format 'Область обл.'"""
    if not region_raw:
        return None
    
    region = region_raw.strip()
    
    # Already formatted
    if region.endswith(' обл.'):
        return region
    
    # Remove 'область' and add 'обл.'
    region = region.replace(' область', '').replace(' Область', '')
    region = region.replace(' обл.', '').replace(' обл', '')
    region = region.strip()
    
    # Capitalize first letter
    if region:
        region = region[0].upper() + region[1:]
        return f"{region} обл."
    
    return None


def _call_api(city: str, region: str = None) -> dict:
    """Make actual API call to OpenCage. Returns {'coords': (lat, lon), 'region': 'X обл.'} or None."""
    _stats['api_calls'] += 1
    
    # Normalize city name (accusative -> nominative)
    city_normalized = _normalize_city_name(city)
    
    # Build query with region context
    if region:
        region_clean = region.replace('область', '').replace('обл.', '').replace('обл', '').strip()
        query = f"{city_normalized}, {region_clean} область, Україна"
    else:
        query = f"{city_normalized}, Україна"
    
    print(f"[GEOCODER] API call #{_stats['api_calls']}: '{query}'", flush=True)
    
    try:
        url = "https://api.opencagedata.com/geocode/v1/json"
        params = {
            'q': query,
            'key': OPENCAGE_API_KEY,
            'countrycode': 'ua',
            'limit': 5,
            'no_annotations': 1,
            'language': 'uk'
        }
        
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 402:
            print("[GEOCODER] QUOTA EXCEEDED!", flush=True)
            return None
        
        if not response.ok:
            print(f"[GEOCODER] API error: {response.status_code}", flush=True)
            return None
        
        data = response.json()
        results = data.get('results', [])
        
        if not results:
            print(f"[GEOCODER] No results for '{city}'", flush=True)
            return None
        
        for r in results:
            components = r.get('components', {})
            
            # Must be in Ukraine
            if components.get('country_code', '').lower() != 'ua':
                continue
            
            geo = r.get('geometry', {})
            lat = geo.get('lat')
            lng = geo.get('lng')
            if not lat or not lng:
                continue
            
            # If region specified, check coords fall within that region
            if region and not _coords_in_oblast(lat, lng, region):
                continue
            
            # Extract region from response
            found_region = components.get('state', '')
            formatted_region = _format_region(found_region)
            
            print(f"[GEOCODER] Found: ({lat:.4f}, {lng:.4f}) in {formatted_region}", flush=True)
            return {'coords': (lat, lng), 'region': formatted_region}
        
        return None
        
    except Exception as e:
        print(f"[GEOCODER] API exception: {e}", flush=True)
        return None


def _call_groq_api(city: str, hint_region: str = None) -> str:
    """
    Use Groq LLM to determine oblast for a Ukrainian city.
    This is a smart fallback when OpenCage fails.
    Returns region in format "Область обл." or None.
    """
    if not GROQ_API_KEY:
        return None
    
    _stats['api_calls'] += 1
    
    # Normalize city name first
    city_normalized = _normalize_city_name(city)
    
    # Build context
    context = f"місто/село: {city_normalized}"
    if hint_region:
        context += f", контекст: {hint_region}"
    
    prompt = f"""Визнач область України для населеного пункту.

{context}

Відповідай ТІЛЬКИ назвою області у форматі "Назва обл." (наприклад: "Дніпропетровська обл.", "Харківська обл.").
Якщо не знаєш або не впевнений - відповідай "невідомо".
Відповідь:"""

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 50,
                "temperature": 0
            },
            timeout=5
        )
        
        if not response.ok:
            print(f"[GROQ] API error: {response.status_code}", flush=True)
            return None
        
        data = response.json()
        answer = data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        
        # Validate answer
        if not answer or 'невідомо' in answer.lower() or len(answer) > 30:
            print(f"[GROQ] No valid answer for '{city}': {answer}", flush=True)
            return None
        
        # Ensure proper format
        if not answer.endswith('обл.'):
            if 'обл' in answer.lower():
                answer = answer.replace('область', 'обл.').replace('обл', 'обл.')
            else:
                answer = answer + ' обл.'
        
        # Clean up
        answer = answer.strip()
        if answer.endswith(' обл. обл.'):
            answer = answer.replace(' обл. обл.', ' обл.')
        
        print(f"[GROQ] Found: {city} -> {answer}", flush=True)
        return answer
        
    except Exception as e:
        print(f"[GROQ] Exception: {e}", flush=True)
        return None


def groq_normalize_city(city: str) -> str:
    """
    🆕 Use Groq to normalize Ukrainian city name to nominative case.
    Handles complex cases that rule-based normalization misses.
    
    Examples:
    - "Софіївки" -> "Софіївка" (genitive)
    - "Кривого Рогу" -> "Кривий Ріг" (genitive)
    - "Синельникового" -> "Синельникове" (genitive)
    - "Балаклію" -> "Балаклія" (accusative)
    """
    if not GROQ_API_KEY or not city or len(city) < 3:
        return city
    
    # First try rule-based normalization
    normalized = _normalize_city_name(city)
    if normalized != city:
        return normalized
    
    _stats['api_calls'] += 1
    
    prompt = f"""Перетвори назву українського населеного пункту в називний відмінок (nominative case).

Вхід: "{city}"

Правила:
- Якщо назва вже в називному відмінку - поверни її без змін
- "Софіївки" (родовий) -> "Софіївка"
- "Кривого Рогу" (родовий) -> "Кривий Ріг"
- "Балаклію" (знахідний) -> "Балаклія"
- "Харкову" (давальний) -> "Харків"

Відповідай ТІЛЬКИ назвою населеного пункту в називному відмінку, без пояснень.
Відповідь:"""

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 30,
                "temperature": 0
            },
            timeout=3
        )
        
        if not response.ok:
            return city
        
        data = response.json()
        answer = data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        
        # Validate - should be similar length, not too different
        if answer and len(answer) <= len(city) + 5 and len(answer) >= len(city) - 5:
            # Capitalize first letter
            answer = answer[0].upper() + answer[1:] if answer else answer
            print(f"[GROQ] Normalized: '{city}' -> '{answer}'", flush=True)
            return answer
        
        return city
        
    except Exception as e:
        print(f"[GROQ] Normalize exception: {e}", flush=True)
        return city


def groq_validate_city_region(city: str, region: str) -> tuple:
    """
    🆕 Use Groq to validate if a city belongs to the given region.
    Returns (city, correct_region) - may correct the region if wrong.
    
    Examples:
    - ("Дослідне", "Одеська обл.") -> ("Дослідне", "Дніпропетровська обл.")
    - ("Харків", "Харківська обл.") -> ("Харків", "Харківська обл.") # no change
    """
    if not GROQ_API_KEY or not city or not region:
        return city, region
    
    _stats['api_calls'] += 1
    
    prompt = f"""Перевір чи населений пункт "{city}" дійсно знаходиться в "{region}".

Якщо ТАК - відповідай: "ПРАВИЛЬНО"
Якщо НІ - відповідай назвою правильної області у форматі "Назва обл."

Приклади:
- Дослідне в "Одеська обл." -> "Дніпропетровська обл." (бо Дослідне в Дніпропетровській)
- Харків в "Харківська обл." -> "ПРАВИЛЬНО"

Відповідь:"""

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 30,
                "temperature": 0
            },
            timeout=3
        )
        
        if not response.ok:
            return city, region
        
        data = response.json()
        answer = data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        
        if 'ПРАВИЛЬНО' in answer.upper():
            return city, region
        
        # Try to extract correct region
        if 'обл' in answer.lower():
            correct_region = answer.strip()
            if not correct_region.endswith('обл.'):
                correct_region = correct_region.replace('область', 'обл.').replace('обл', 'обл.')
            print(f"[GROQ] Validated: {city} ({region}) -> ({correct_region})", flush=True)
            return city, correct_region
        
        return city, region
        
    except Exception as e:
        print(f"[GROQ] Validate exception: {e}", flush=True)
        return city, region


def groq_parse_message(text: str) -> list:
    """
    🆕 Use Groq to parse a message and extract cities with regions.
    This is a smart fallback when regex patterns fail.
    
    Returns list of dicts: [{"city": "Харків", "region": "Харківська обл.", "type": "БПЛА"}, ...]
    """
    if not GROQ_API_KEY or not text or len(text) < 10:
        return []
    
    _stats['api_calls'] += 1
    
    prompt = f"""Проаналізуй повідомлення про загрози БПЛА/ракет і витягни інформацію про міста.

Повідомлення:
"{text}"

Для кожного згаданого населеного пункту вкажи:
1. Назва міста/села в називному відмінку
2. Область (у форматі "Назва обл.")
3. Тип загрози: БПЛА, Ракета, КАБ або Вибухи

Формат відповіді (JSON array):
[{{"city": "Місто", "region": "Область обл.", "type": "БПЛА"}}]

Якщо міст немає - відповідай: []

Жаргон:
- "балалайка", "мопед", "герань", "шахед" = БПЛА
- "баллістика", "ракета", "калібр" = Ракета

Відповідь:"""

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
                "temperature": 0
            },
            timeout=5
        )
        
        if not response.ok:
            print(f"[GROQ] Parse API error: {response.status_code}", flush=True)
            return []
        
        data = response.json()
        answer = data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        
        # Try to parse JSON
        import re
        json_match = re.search(r'\[.*\]', answer, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group())
                if isinstance(result, list):
                    # Validate and clean results
                    cleaned = []
                    for item in result:
                        if isinstance(item, dict) and 'city' in item:
                            city = item.get('city', '').strip()
                            region = item.get('region', '').strip()
                            threat_type = item.get('type', 'БПЛА').strip()
                            if city and region:
                                # Ensure region format
                                if not region.endswith('обл.'):
                                    region = region.replace('область', 'обл.').replace('обл', 'обл.')
                                cleaned.append({
                                    'city': city,
                                    'region': region,
                                    'type': threat_type
                                })
                    if cleaned:
                        print(f"[GROQ] Parsed: {cleaned}", flush=True)
                    return cleaned
            except json.JSONDecodeError:
                pass
        
        return []
        
    except Exception as e:
        print(f"[GROQ] Parse exception: {e}", flush=True)
        return []


def groq_translate_russian(city_ru: str) -> str:
    """
    🆕 Translate Russian city name to Ukrainian.
    
    Examples:
    - "Кривой Рог" -> "Кривий Ріг"
    - "Днепр" -> "Дніпро"
    - "Николаев" -> "Миколаїв"
    """
    if not GROQ_API_KEY or not city_ru:
        return city_ru
    
    # Quick check for common Russian names
    ru_to_ua = {
        'кривой рог': 'Кривий Ріг',
        'днепр': 'Дніпро',
        'николаев': 'Миколаїв',
        'харьков': 'Харків',
        'киев': 'Київ',
        'одесса': 'Одеса',
        'запорожье': 'Запоріжжя',
        'херсон': 'Херсон',
        'чернигов': 'Чернігів',
        'сумы': 'Суми',
        'полтава': 'Полтава',
        'черкассы': 'Черкаси',
        'кременчуг': 'Кременчук',
        'мариуполь': 'Маріуполь',
        'мелитополь': 'Мелітополь',
        'бердянск': 'Бердянськ',
        'павлоград': 'Павлоград',
        'кропивницкий': 'Кропивницький',
        'житомир': 'Житомир',
        'винница': 'Вінниця',
        'ровно': 'Рівне',
        'луцк': 'Луцьк',
        'львов': 'Львів',
        'ивано-франковск': 'Івано-Франківськ',
        'тернополь': 'Тернопіль',
        'хмельницкий': 'Хмельницький',
        'ужгород': 'Ужгород',
        'черновцы': 'Чернівці',
        'изюм': 'Ізюм',
        'купянск': 'Куп\'янськ',
        'славянск': 'Слов\'янськ',
        'краматорск': 'Краматорськ',
        'бахмут': 'Бахмут',
        'покровск': 'Покровськ',
        'черноморск': 'Чорноморськ',
    }
    
    city_lower = city_ru.lower().strip()
    if city_lower in ru_to_ua:
        return ru_to_ua[city_lower]
    
    # Check if it looks Russian (has ы, э, ъ, ё or other Russian-specific chars)
    russian_chars = set('ыэъёЫЭЪЁ')
    if not any(c in city_ru for c in russian_chars):
        # Might already be Ukrainian or transliterated
        return city_ru
    
    _stats['api_calls'] += 1
    
    prompt = f"""Перекладі російську назву міста на українську.

Російська назва: "{city_ru}"

Відповідай ТІЛЬКИ українською назвою міста.
Приклади: "Кривой Рог" -> "Кривий Ріг", "Днепр" -> "Дніпро"

Відповідь:"""

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 30,
                "temperature": 0
            },
            timeout=3
        )
        
        if not response.ok:
            return city_ru
        
        data = response.json()
        answer = data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        
        if answer and len(answer) <= len(city_ru) + 10:
            print(f"[GROQ] Translated: '{city_ru}' -> '{answer}'", flush=True)
            return answer
        
        return city_ru
        
    except Exception as e:
        print(f"[GROQ] Translate exception: {e}", flush=True)
        return city_ru


def get_region(city: str, hint_region: str = None) -> str:
    """
    Get oblast (region) for a city. Uses cache first, then OpenCage, then Groq AI.
    
    Args:
        city: City name (can be in any grammatical case)
        hint_region: Optional hint about region (for disambiguation)
    
    Returns: Region name in format "Область обл." or None
    """
    if not city or len(city) < 2:
        return None
    
    cache_key = _normalize_key(city, hint_region)
    if not cache_key:
        return None
    
    # Check positive cache
    if cache_key in _cache:
        _stats['hits'] += 1
        cached = _cache[cache_key]
        if isinstance(cached, dict):
            return cached.get('region')
        return None
    
    # Check negative cache
    if cache_key in _negative_cache:
        _stats['hits'] += 1
        return None
    
    # Try OpenCage API first
    _stats['misses'] += 1
    result = _call_api(city, hint_region)
    
    if result and result.get('region'):
        _cache[cache_key] = result
        _save_cache()
        return result.get('region')
    
    # Fallback to Groq AI
    groq_region = _call_groq_api(city, hint_region)
    if groq_region:
        # Cache the result (without coords since Groq doesn't provide them)
        _cache[cache_key] = {'coords': None, 'region': groq_region}
        _save_cache()
        return groq_region
    
    # Nothing found - add to negative cache
    _negative_cache.add(cache_key)
    _save_negative_cache()
    return None


def geocode(city: str, region: str = None) -> tuple:
    """
    Geocode a city. Returns (lat, lon) tuple or None.
    """
    if not city or len(city) < 2:
        return None
    
    cache_key = _normalize_key(city, region)
    if not cache_key:
        return None
    
    # Check positive cache
    if cache_key in _cache:
        _stats['hits'] += 1
        cached = _cache[cache_key]
        if isinstance(cached, dict):
            return cached.get('coords')
        return cached if isinstance(cached, tuple) else None
    
    # Check negative cache
    if cache_key in _negative_cache:
        _stats['hits'] += 1
        return None
    
    # Call API
    _stats['misses'] += 1
    result = _call_api(city, region)
    
    if result:
        _cache[cache_key] = result
        _save_cache()
        return result.get('coords')
    else:
        _negative_cache.add(cache_key)
        _save_negative_cache()
        return None


def get_cache_stats() -> dict:
    """Get geocoding statistics"""
    return {
        'cached': len(_cache),
        'negative_cached': len(_negative_cache),
        'hits': _stats['hits'],
        'misses': _stats['misses'],
        'api_calls': _stats['api_calls']
    }


# Load cache on module import
_load_cache()
