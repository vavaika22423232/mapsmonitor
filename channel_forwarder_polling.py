#!/usr/bin/env python3
"""
Channel Forwarder з polling (опитування)
Перевіряє канали кожні 30 секунд
Оптимізовано для Render.com
"""

import asyncio
import logging
import re
import aiohttp
import time
from telethon import TelegramClient
from telethon.sessions import StringSession
import os
import sys

# Імпортуємо геокодер для автоматичного визначення області
try:
    from geocoder import get_region as geocoder_get_region
    GEOCODER_AVAILABLE = True
    print("[INFO] Geocoder module loaded successfully", flush=True)
except ImportError:
    GEOCODER_AVAILABLE = False
    print("[WARNING] Geocoder module not available, using fallback", flush=True)

logging.basicConfig(
    format='[%(levelname)s/%(asctime)s] %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфігурація з environment variables
API_ID = os.getenv('TELEGRAM_API_ID')
API_HASH = os.getenv('TELEGRAM_API_HASH')
STRING_SESSION = os.getenv('TELEGRAM_SESSION')

SOURCE_CHANNELS = os.getenv('SOURCE_CHANNELS', 'UkraineAlarmSignal,war_monitor,napramok,ukrainsiypposhnik,radarzagrozi,povitryanatrivogaaa,raketa_trevoga,monikppy').split(',')
TARGET_CHANNEL = os.getenv('TARGET_CHANNEL', 'mapstransler')

# Інтервал опитування (секунди)
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '30'))

# Інтервал дедуплікації (секунди) - 5 хвилин
DEDUP_INTERVAL = int(os.getenv('DEDUP_INTERVAL', '300'))

# Перевірка обов'язкових змінних
if not API_ID or not API_HASH:
    logger.error("❌ TELEGRAM_API_ID та TELEGRAM_API_HASH обов'язкові!")
    sys.exit(1)

if not STRING_SESSION:
    logger.error("❌ TELEGRAM_SESSION обов'язкова!")
    sys.exit(1)

try:
    API_ID = int(API_ID)
except ValueError:
    logger.error("❌ TELEGRAM_API_ID має бути числом!")
    sys.exit(1)

# Словник для зберігання ID останніх переслані повідомлень
last_message_ids = {}

# Кеш для дедуплікації повідомлень (місто -> timestamp)
sent_locations_cache = {}

# Клієнт з StringSession для Render
client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)


def normalize_location(message):
    """
    Витягує ключ локації з повідомлення для дедуплікації.
    Наприклад: "БПЛА Харків (Харківська обл.) Загроза..." -> "харків_харківська обл."
    """
    # Шукаємо паттерн "Місто (Область)"
    match = re.search(r'(?:БПЛА\s+)?([^(]+)\s*\(([^)]+)\)', message)
    if match:
        city = match.group(1).strip().lower()
        region = match.group(2).strip().lower()
        # Видаляємо зайві слова
        city = re.sub(r'^\d+х\s+', '', city)  # Видаляємо "3х " на початку
        city = re.sub(r'^бпла\s+', '', city)  # Видаляємо "бпла " на початку
        city = re.sub(r'\s+район$', '', city)  # Видаляємо " район" в кінці
        return f"{city}_{region}"
    return None


def is_duplicate(message):
    """
    Перевіряє чи повідомлення є дублікатом (вже відправлялось за останні DEDUP_INTERVAL секунд)
    """
    location_key = normalize_location(message)
    if not location_key:
        return False
    
    current_time = time.time()
    
    # Очищаємо старі записи з кешу
    keys_to_remove = [k for k, v in sent_locations_cache.items() if current_time - v > DEDUP_INTERVAL]
    for k in keys_to_remove:
        del sent_locations_cache[k]
    
    # Перевіряємо чи є в кеші
    if location_key in sent_locations_cache:
        time_diff = current_time - sent_locations_cache[location_key]
        logger.info(f"⏭️ Пропуск дубліката: {location_key} (було {int(time_diff)} сек тому)")
        return True
    
    return False


def mark_as_sent(message):
    """
    Позначає повідомлення як відправлене
    """
    location_key = normalize_location(message)
    if location_key:
        sent_locations_cache[location_key] = time.time()
        logger.info(f"📝 Збережено в кеш: {location_key}")


# Мапінг регіонів на українську мову
REGION_MAP = {
    'Сумщина': 'Сумська обл.',
    'Сумщини': 'Сумська обл.',
    'Сумщину': 'Сумська обл.',
    'Чернігівщина': 'Чернігівська обл.',
    'Чернігівщини': 'Чернігівська обл.',
    'Чернігівщину': 'Чернігівська обл.',
    'Полтавщина': 'Полтавська обл.',
    'Полтавщини': 'Полтавська обл.',
    'Полтавщину': 'Полтавська обл.',
    'Черкащина': 'Черкаська обл.',
    'Черкащини': 'Черкаська обл.',
    'Черкащину': 'Черкаська обл.',
    'Київщина': 'Київська обл.',
    'Київщини': 'Київська обл.',
    'Київщину': 'Київська обл.',
    'Харківщина': 'Харківська обл.',
    'Харківщини': 'Харківська обл.',
    'Харківщину': 'Харківська обл.',
    'Дніпропетровщина': 'Дніпропетровська обл.',
    'Дніпропетровщини': 'Дніпропетровська обл.',
    'Дніпропетровщину': 'Дніпропетровська обл.',
    'Миколаївщина': 'Миколаївська обл.',
    'Миколаївщини': 'Миколаївська обл.',
    'Миколаївщину': 'Миколаївська обл.',
    'Одещина': 'Одеська обл.',
    'Одещини': 'Одеська обл.',
    'Одещину': 'Одеська обл.',
    'Херсонщина': 'Херсонська обл.',
    'Херсонщини': 'Херсонська обл.',
    'Херсонщину': 'Херсонська обл.',
    'Запорізька': 'Запорізька обл.',
    'Запоріжжя': 'Запорізька обл.',
    'Донеччина': 'Донецька обл.',
    'Донеччини': 'Донецька обл.',
    'Донеччину': 'Донецька обл.',
    'Луганщина': 'Луганська обл.',
    'Луганщини': 'Луганська обл.',
    'Луганщину': 'Луганська обл.',
    'Житомирщина': 'Житомирська обл.',
    'Житомирщини': 'Житомирська обл.',
    'Житомирщину': 'Житомирська обл.',
    'Вінниччина': 'Вінницька обл.',
    'Вінниччини': 'Вінницька обл.',
    'Вінниччину': 'Вінницька обл.',
    'Хмельниччина': 'Хмельницька обл.',
    'Хмельниччини': 'Хмельницька обл.',
    'Хмельниччину': 'Хмельницька обл.',
    'Рівненщина': 'Рівненська обл.',
    'Рівненщини': 'Рівненська обл.',
    'Рівненщину': 'Рівненська обл.',
    'Волинь': 'Волинська обл.',
    'Волині': 'Волинська обл.',
    'Львівщина': 'Львівська обл.',
    'Львівщини': 'Львівська обл.',
    'Львівщину': 'Львівська обл.',
    'Тернопільщина': 'Тернопільська обл.',
    'Тернопільщини': 'Тернопільська обл.',
    'Тернопільщину': 'Тернопільська обл.',
    'Івано-Франківщина': 'Івано-Франківська обл.',
    'Івано-Франківщини': 'Івано-Франківська обл.',
    'Івано-Франківщину': 'Івано-Франківська обл.',
    'Закарпаття': 'Закарпатська обл.',
    'Закарпаттю': 'Закарпатська обл.',
    'Кіровоградщина': 'Кіровоградська обл.',
    'Кіровоградщини': 'Кіровоградська обл.',
    'Кіровоградщину': 'Кіровоградська обл.'
}

# Мапінг міст на області (обласні центри та великі міста)
# Мінімальний словник для швидкого пошуку (обласні центри) - решта через геокодер
CITY_TO_REGION = {
    'Київ': 'Київська обл.',
    'Харків': 'Харківська обл.',
    'Одеса': 'Одеська обл.',
    'Дніпро': 'Дніпропетровська обл.',
    'Донецьк': 'Донецька обл.',
    'Запоріжжя': 'Запорізька обл.',
    'Львів': 'Львівська обл.',
    'Кривий Ріг': 'Дніпропетровська обл.',
    'Миколаїв': 'Миколаївська обл.',
    'Луганськ': 'Луганська обл.',
    'Вінниця': 'Вінницька обл.',
    'Херсон': 'Херсонська обл.',
    'Полтава': 'Полтавська обл.',
    'Чернігів': 'Чернігівська обл.',
    'Черкаси': 'Черкаська обл.',
    'Житомир': 'Житомирська обл.',
    'Суми': 'Сумська обл.',
    'Хмельницький': 'Хмельницька обл.',
    'Рівне': 'Рівненська обл.',
    'Івано-Франківськ': 'Івано-Франківська обл.',
    'Тернопіль': 'Тернопільська обл.',
    'Луцьк': 'Волинська обл.',
    'Ужгород': 'Закарпатська обл.',
    'Кропивницький': 'Кіровоградська обл.',
    # Спеціальні локації
    'Чорне море': 'Одеська обл.',
    'Чорному морі': 'Одеська обл.',
}

# Кеш для геокодингу (щоб не робити зайвих запитів) - використовується як fallback
geo_cache = {}

async def get_region_by_city(city_name, hint_region=None):
    """
    Отримує область за назвою міста.
    Спочатку пробує OpenCage геокодер, потім локальний словник, потім Nominatim.
    """
    # Спочатку перевіряємо локальний словник (швидко і безкоштовно)
    if city_name in CITY_TO_REGION:
        return CITY_TO_REGION[city_name]
    
    # Пробуємо OpenCage геокодер (з кешуванням)
    if GEOCODER_AVAILABLE:
        try:
            region = geocoder_get_region(city_name, hint_region)
            if region:
                logger.info(f"🌍 Геокодер: {city_name} -> {region}")
                return region
        except Exception as e:
            logger.warning(f"⚠️ Помилка геокодера для {city_name}: {e}")
    
    # Перевіряємо локальний кеш
    if city_name in geo_cache:
        return geo_cache[city_name]
    
    # Fallback: Nominatim API (OpenStreetMap)
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': f"{city_name}, Україна",
            'format': 'json',
            'addressdetails': 1,
            'limit': 1,
            'accept-language': 'uk'
        }
        headers = {
            'User-Agent': 'TelegramForwarder/1.0'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and len(data) > 0:
                        address = data[0].get('address', {})
                        # Шукаємо область
                        region = address.get('state', '')
                        if region:
                            # Приводимо до формату "Область обл."
                            if 'область' in region.lower():
                                region = region.replace('область', 'обл.').replace('Область', 'обл.')
                            elif not region.endswith('обл.'):
                                region = region + ' обл.'
                            
                            # Зберігаємо в кеш
                            geo_cache[city_name] = region
                            logger.info(f"🌍 Nominatim: {city_name} -> {region}")
                            return region
    except asyncio.TimeoutError:
        logger.warning(f"⚠️ Таймаут геокодингу для {city_name}")
    except Exception as e:
        logger.warning(f"⚠️ Помилка геокодингу для {city_name}: {e}")
    
    # Зберігаємо None в кеш щоб не повторювати запити
    geo_cache[city_name] = None
    return None


def clean_text(text):
    """
    Очищає текст від зайвої інформації та посилань
    """
    if not text:
        return text
    
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Пропускаємо порожні рядки та рядки з лише пробілами/спецсимволами
        if not line.strip() or line.strip() in ['ㅤ', '─' * len(line.strip())]:
            continue
        
        # Пропускаємо рядки з "Підписатися", "ППОшник", "Monitorzagroz" тощо
        skip_keywords = ['Підписатися', 'ППОшник', 'Підпис', 'Telegram', 'Channel', 'Моніторинг 24/7', 'Напрямок ракет', 'Підтримати канал', 'Радар України']
        if any(keyword in line for keyword in skip_keywords):
            continue
        
        # Пропускаємо рядки що містять тільки стрілки, флаги та символи
        if re.match(r'^[➡️⬅️↗️↘️↖️↙️⬆️⬇️🇺🇦\s|]+$', line):
            continue
        
        # Видаляємо посилання (URLs)
        line = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', line)
        
        # Видаляємо @username
        line = re.sub(r'@\w+', '', line)
        
        # Видаляємо зайві пробіли
        line = ' '.join(line.split())
        
        if line.strip():
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)


async def split_cities(city_string):
    """
    Розділяє рядок з кількома містами (через / або ,) на список окремих міст
    Повертає перше місто (вибираємо одне)
    """
    # Видаляємо "з області" частину (напр. "Дубровицю з Житомирщини" -> "Дубровицю")
    city_string = re.sub(r'\s+з\s+\S+$', '', city_string)
    
    # Розділяємо по / або ,
    if '/' in city_string:
        cities = city_string.split('/')
        city = cities[0].strip()
    elif ',' in city_string and 'обл' not in city_string.lower():
        cities = city_string.split(',')
        city = cities[0].strip()
    else:
        city = city_string.strip()
    
    # Видаляємо крапку та інші зайві символи в кінці назви міста
    city = city.rstrip('.!?,;:')
    
    return city


def fix_city_case(city):
    """
    Виправляє відмінок назви міста - використовує геокодер для нормалізації.
    Якщо геокодер недоступний, повертає як є.
    """
    if not city:
        return city
    
    # Використовуємо геокодер для нормалізації (він має _normalize_city_name)
    if GEOCODER_AVAILABLE:
        try:
            from geocoder import _normalize_city_name
            return _normalize_city_name(city)
        except:
            pass
    
    # Базова нормалізація якщо геокодер недоступний
    city = city.strip()
    
    # -ого -> -е (Синельникового -> Синельникове)
    if city.endswith('ого') and len(city) > 4:
        return city[:-3] + 'е'
    
    # -ку -> -ка (знахідний)
    if city.endswith('ку') and len(city) > 3:
        return city[:-1] + 'а'
    
    return city


async def parse_and_split_message(text):
    """
    Розбиває повідомлення на окремі повідомлення по населених пунктах
    """
    if not text:
        return []
    
    # Спочатку очищаємо текст
    text = clean_text(text)
    
    # Обробка повідомлень про відбій балістики
    # Формат: "⚪️Відбій загрози застосування балістичного озброєння"
    vidbiy_balistyka_match = re.search(r'[Вв]ідбій\s+загрози\s+застосування\s+балістичн', text, re.IGNORECASE)
    if vidbiy_balistyka_match:
        return ["Відбій загрози балістики!"]
    
    # Обробка повідомлень про КАБи окремо
    # Формат: "💣 Місто (Область) Загроза застосування КАБів..."
    kab_match = re.search(r'^[💣⚠️❗️\s]*(.+?)\s*\((.+?обл\.?)\)\s*\n?\s*Загроза\s+застосування\s+КАБів', text, re.IGNORECASE | re.MULTILINE)
    if kab_match:
        location = kab_match.group(1).strip()
        region = kab_match.group(2).strip()
        if not region.endswith('.'):
            region = region + '.'
        msg = f"{location} ({region})\nЗагроза застосування КАБів."
        return [msg]
    
    # Обробка повідомлень про вибухи окремо
    # Формат: "⚠️ Місто (Область) ЗМІ повідомляють про вибухи..." або "⚠️ Місто (Область)\nЗМІ повідомляють..."
    vybukhy_match = re.search(r'^[⚠️❗️💥\s]*(.+?)\s*\((.+?обл\.?)\)[\s\n]*(?:ЗМІ\s+)?повідомляють\s+про\s+вибухи', text, re.IGNORECASE | re.MULTILINE)
    if vybukhy_match:
        location = vybukhy_match.group(1).strip()
        region = vybukhy_match.group(2).strip()
        if not region.endswith('.'):
            region = region + '.'
        msg = f"{location} ({region})\nвибухи."
        return [msg]
    
    # Формат: "💥 Павлоград - вибухи" (без області в дужках)
    vybukhy_no_region_match = re.search(r'^[⚠️❗️💥\s]*(.+?)\s*[-–—]\s*вибух', text, re.IGNORECASE | re.MULTILINE)
    if vybukhy_no_region_match:
        city = vybukhy_no_region_match.group(1).strip()
        # Видаляємо emoji з назви міста
        city = re.sub(r'^[💥⚠️❗️\s]+', '', city).strip()
        if city:
            # Використовуємо геокодер для визначення області
            region = None
            if GEOCODER_AVAILABLE:
                region = geocoder_get_region(city)
            if not region:
                region = CITY_TO_REGION.get(city)
            if region:
                if not region.endswith('.'):
                    region = region + '.'
                msg = f"{city} ({region})\nвибухи."
                return [msg]
    
    # Обробка повідомлень про високошвидкісні цілі (ракети)
    # Формат: "🚀 Харків (Харківська обл.) Загроза застосування високошвидкісних цілей..."
    raketa_match = re.search(r'^[🚀⚠️❗️\s]*(.+?)\s*\((.+?обл\.?)\)[\s\n]*Загроза\s+застосування\s+високошвидкісних\s+цілей', text, re.IGNORECASE | re.MULTILINE)
    if raketa_match:
        location = raketa_match.group(1).strip()
        region = raketa_match.group(2).strip()
        if not region.endswith('.'):
            region = region + '.'
        msg = f"Ракета {location} ({region})"
        return [msg]
    
    # Пропускаємо повідомлення про загрози обстрілу, укриття тощо (АЛЕ НЕ вибухи, ракети та БПЛА!)
    if re.search(r'загроза\s+обстрілу|перейдіть\s+в\s+укриття|прямуйте\s+в\s+укриття|негайно\s+прямуйте', text, re.IGNORECASE):
        # Перевіряємо чи це не повідомлення про вибухи, ракети або БПЛА
        if not re.search(r'вибух|високошвидкісн|загроза\s+застосування\s+БПЛА', text, re.IGNORECASE):
            return []
    
    # Окрема перевірка "будьте обережні" - пропускаємо тільки якщо немає інфи про вибухи/БПЛА
    if re.search(r'будьте\s+обережні', text, re.IGNORECASE):
        if not re.search(r'вибух|високошвидкісн|загроза\s+застосування\s+БПЛА', text, re.IGNORECASE):
            return []
    
    messages = []
    lines = text.strip().split('\n')
    current_region = None
    current_city = None  # Для контексту районів міста (напр. "Кривий Ріг:")
    
    # Зберігаємо наступний рядок як опис загрози
    lines_list = text.strip().split('\n')
    threat_descriptions = {}
    for i, line in enumerate(lines_list):
        if i + 1 < len(lines_list):
            next_line = lines_list[i + 1].strip()
            if next_line and not re.match(r'^[💥🛸🛵⚠️❗️🔴👁️]', next_line):
                threat_descriptions[i] = next_line
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # Пропускаємо повідомлення про повітряну тривогу, відбій та загрозу обстрілу (не БПЛА/КАБ)
        # НЕ пропускаємо "будьте обережні" - воно може бути частиною повідомлення про вибухи
        if re.search(r'повітряна\s+тривога|відбій\s+тривоги|прямуйте\s+в\s+укриття|перейдіть\s+в\s+укриття|загроза\s+обстрілу', line, re.IGNORECASE):
            continue
        
        # Формат заголовка: "✈️Дніпропетровщина:" або "🛵Харківщина:" або просто "Дніпропетровщина:" - область з/без emoji і двокрапкою
        emoji_region_header_match = re.match(r'^[✈️🛵🛸⚠️\s]*(\S+):\s*$', line, re.IGNORECASE)
        if emoji_region_header_match:
            short_region = emoji_region_header_match.group(1).strip()
            region = REGION_MAP.get(short_region, None)
            if region:
                current_region = region
                current_city = None  # Скидаємо поточне місто
            continue
        
        # Формат заголовка міста: "⚠️ Кривий Ріг:" або "Кривий Ріг:" - місто з двокрапкою (для районів міста)
        city_header_match = re.match(r'^[⚠️‼️\s]*(.+?):\s*$', line, re.IGNORECASE)
        if city_header_match:
            potential_city = city_header_match.group(1).strip()
            # Перевіряємо чи це місто, а не область
            if potential_city in CITY_TO_REGION:
                current_city = potential_city
                current_region = CITY_TO_REGION[potential_city]
                continue
            # Також перевіряємо область
            region = REGION_MAP.get(potential_city, None)
            if region:
                current_region = region
                current_city = None
                continue
        
        # Формат: "‼️ Кривий Ріг - 7 шахедів заходять на місто" - місто з тире
        city_dash_match = re.match(r'^[⚠️‼️\s]*(.+?)\s*[-–—]\s*\d*\s*шахед', line, re.IGNORECASE)
        if city_dash_match:
            city = city_dash_match.group(1).strip()
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            region = CITY_TO_REGION.get(city, None)
            if not region:
                region = await get_region_by_city(city)
            if region:
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
                continue
        
        # Формат: "Шахед від X повернувся на Y" або "Шахед знову на Y"
        shahed_na_match = re.match(r'^[Шш]ахед\s+(?:від\s+\S+\s+)?(?:повернувся|знову)\s+на\s+(\S+)', line, re.IGNORECASE)
        if shahed_na_match:
            city = shahed_na_match.group(1).strip()
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            region = current_region
            if not region:
                region = CITY_TO_REGION.get(city, None)
            if not region:
                region = await get_region_by_city(city)
            if region:
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
                continue
        
        # Формат: "Шахед курсом на X" (в контексті міста)
        shahed_kursom_match = re.match(r'^[Шш]ахед\s+курсом\s+на\s+(\S+)', line, re.IGNORECASE)
        if shahed_kursom_match:
            city = shahed_kursom_match.group(1).strip()
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            region = current_region
            if not region:
                region = CITY_TO_REGION.get(city, None)
            if not region:
                region = await get_region_by_city(city)
            if region:
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
                continue
        
        # Формат: "N крутиться/кружляє біля X" 
        krutytsya_match = re.match(r'^\d+\s+(?:крутиться|кружляє|кружляють)\s+біля\s+(\S+)', line, re.IGNORECASE)
        if krutytsya_match:
            city = krutytsya_match.group(1).strip()
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            region = current_region
            if not region:
                region = CITY_TO_REGION.get(city, None)
            if not region:
                region = await get_region_by_city(city)
            if region:
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
                continue
        
        # Формат: "N шахеди/шахедів на X з Y" або "N шахеди на X"
        shahedy_na_match = re.match(r'^\d+\s+шахед[іиів]*\s+на\s+(\S+)(?:\s+з\s+.+)?', line, re.IGNORECASE)
        if shahedy_na_match:
            city = shahedy_na_match.group(1).strip()
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            region = current_region
            if not region:
                region = CITY_TO_REGION.get(city, None)
            if not region:
                region = await get_region_by_city(city)
            if region:
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
                continue
        
        # Формат: "6 шахедів в Чорному морі" або "N шахедів в/у локації"
        shahedy_v_match = re.match(r'^(\d+)\s+шахед[іиів]*\s+[ву]\s+(.+?)$', line, re.IGNORECASE)
        if shahedy_v_match:
            location = shahedy_v_match.group(2).strip()
            # Перевіряємо чи є в словнику (напр. "Чорному морі")
            region = CITY_TO_REGION.get(location, None)
            if region:
                # Нормалізуємо назву (Чорному морі -> Чорне море)
                if 'морі' in location.lower():
                    location = 'Чорне море'
                msg = f"БПЛА {location} ({region})"
                messages.append(msg)
                continue
        
        # Формат: "На Кривий Ріг вже N шт" або "На X заходять"
        na_city_match = re.match(r'^[Нн]а\s+(.+?)\s+(?:вже|заходять|заходить|летить|летять)', line, re.IGNORECASE)
        if na_city_match:
            city = na_city_match.group(1).strip()
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            region = CITY_TO_REGION.get(city, None)
            if not region:
                region = await get_region_by_city(city)
            if region:
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
                continue
        
        # Формат: "1 Арселор" або "1 на п'ятий Зарічний" або "1 в районі X" (в контексті current_city)
        rayon_match = re.match(r'^\d+\s+(?:на\s+(?:п\'ятий\s+)?|в\s+район[іу]\s+)?(\S+)\s*$', line, re.IGNORECASE)
        if rayon_match and current_city and current_region:
            rayon = rayon_match.group(1).strip()
            # Якщо це район міста, виводимо місто
            msg = f"БПЛА {current_city} ({current_region})"
            if msg not in messages:  # Уникаємо дублікатів
                messages.append(msg)
            continue
        
        # Формат: "N в напрямку Міста" або "N в напрямку Міста (нові)"
        v_napryamku_match = re.match(r'^(\d+)\s+в\s+напрямку\s+(\S+)(?:\s*\([^)]*\))?', line, re.IGNORECASE)
        if v_napryamku_match and current_region:
            city = v_napryamku_match.group(2).strip()
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            msg = f"БПЛА {city} ({current_region})"
            messages.append(msg)
            continue
        
        # Формат: "N на Місто від X" (напр. "1 на Петрове від Кривого Рогу")
        na_vid_match = re.match(r'^(\d+)\s+на\s+(\S+)\s+від\s+', line, re.IGNORECASE)
        if na_vid_match and current_region:
            city = na_vid_match.group(2).strip()
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            msg = f"БПЛА {city} ({current_region})"
            messages.append(msg)
            continue
        
        # Формат зі стрілкою: "→Павлоград/р-н (кружляє);" або "→Кривий Ріг/р-н."
        arrow_city_match = re.match(r'^[→➡️\s]*(.+?)/р-н\.?(?:\s*\([^)]*\))?[;\.]*\s*$', line, re.IGNORECASE)
        if arrow_city_match and current_region:
            city = arrow_city_match.group(1).strip()
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            msg = f"БПЛА {city} ({current_region})"
            messages.append(msg)
            continue
        
        # Формат заголовка: "4 шахеди на Чернігівщині:" або "1 шахед на Полтавщині:"
        header_region_match = re.match(r'^\d+\s+(?:шахед[іиів]*|БпЛА|БПЛА)\s+на\s+(\S+):?\s*$', line, re.IGNORECASE)
        if header_region_match:
            short_region = header_region_match.group(1).strip().rstrip(':')
            region = REGION_MAP.get(short_region, None)
            if region:
                current_region = region
            continue
        
        # Формат: "1 повз Славутич південним курсом" або "2 на Сновськ зі сходу"
        povz_city_match = re.match(r'^\d+\s+(?:повз|на)\s+(\S+)(?:\s+.+)?$', line, re.IGNORECASE)
        if povz_city_match and current_region:
            city = povz_city_match.group(1).strip()
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            msg = f"БПЛА {city} ({current_region})"
            messages.append(msg)
            continue
        
        # Формат: "1 кружляє між Гадячем та Зіньковом" або "1 крутиться в районі X" - беремо перше місто
        kruzhlyaye_match = re.match(r'^\d+\s+(?:кружляє|крутиться|крутяться)\s+(?:між|біля|в районі|в район|в)\s+(\S+)(?:\s+та\s+.+)?$', line, re.IGNORECASE)
        if kruzhlyaye_match and current_region:
            city = kruzhlyaye_match.group(1).strip()
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            # Перевіряємо чи це "морі" -> Чорне море
            if city.lower() == 'морі':
                city = 'Чорне море'
            msg = f"БПЛА {city} ({current_region})"
            messages.append(msg)
            continue
        
        # Формат: "1 маневрує північніше Кам'янського"
        manevruje_match = re.match(r'^\d+\s+маневрує\s+(?:північніше|південніше|західніше|східніше|біля)\s+(\S+)$', line, re.IGNORECASE)
        if manevruje_match and current_region:
            city = manevruje_match.group(1).strip()
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            msg = f"БПЛА {city} ({current_region})"
            messages.append(msg)
            continue
        
        # Формат: "2 в районі Васильківки" або "1 в район Кам'янського"
        v_rayoni_simple_match = re.match(r'^(\d+)\s+в\s+район[іу]?\s+(\S+)$', line, re.IGNORECASE)
        if v_rayoni_simple_match and current_region:
            city = v_rayoni_simple_match.group(2).strip()
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            msg = f"БПЛА {city} ({current_region})"
            messages.append(msg)
            continue
        
        # Формат: "1 над лівобережжям Дніпра" або "2 над Кривим Рогом"
        nad_match = re.match(r'^(\d+)\s+над\s+(?:лівобережжям|правобережжям)?\s*(\S+)$', line, re.IGNORECASE)
        if nad_match and current_region:
            city = nad_match.group(2).strip()
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            msg = f"БПЛА {city} ({current_region})"
            messages.append(msg)
            continue
        
        # Формат: "1 на Лозуватку (через це тривога...)" або "1 південніше Дніпра (Тополя)" - місто з поясненням в дужках
        na_city_poyasn_match = re.match(r'^(\d+)\s+(?:на|південніше|північніше|західніше|східніше)\s+(\S+)\s*\([^)]+\)$', line, re.IGNORECASE)
        if na_city_poyasn_match and current_region:
            city = na_city_poyasn_match.group(2).strip()
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            msg = f"БПЛА {city} ({current_region})"
            messages.append(msg)
            continue
        
        # Формат: "Шахед курсом на Шостку" - без кількості
        shahed_kursom_match = re.match(r'^[Шш]ахед\s+курсом\s+на\s+(\S+)$', line, re.IGNORECASE)
        if shahed_kursom_match and current_region:
            city = shahed_kursom_match.group(1).strip()
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            msg = f"БПЛА {city} ({current_region})"
            messages.append(msg)
            continue
        
        # Формат: "3 курсом на Татарбунари" - N курсом на X
        n_kursom_match = re.match(r'^(\d+)\s+курсом\s+на\s+(\S+)$', line, re.IGNORECASE)
        if n_kursom_match and current_region:
            city = n_kursom_match.group(2).strip()
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            msg = f"БПЛА {city} ({current_region})"
            messages.append(msg)
            continue
        
        # Формат: "1 на/через Славгород" - на/через або на Місто
        na_cherez_match = re.match(r'^(\d+)\s+(?:на/через|через)\s+(\S+)$', line, re.IGNORECASE)
        if na_cherez_match and current_region:
            city = na_cherez_match.group(2).strip()
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            msg = f"БПЛА {city} ({current_region})"
            messages.append(msg)
            continue
        
        # Формат: "2 Синельникове / Васильківка" - N Місто1 / Місто2 (беремо перше)
        n_cities_match = re.match(r'^(\d+)\s+(\S+)\s*/\s*(\S+)$', line, re.IGNORECASE)
        if n_cities_match and current_region:
            city = n_cities_match.group(2).strip()
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            msg = f"БПЛА {city} ({current_region})"
            messages.append(msg)
            continue
        
        # Формат: "БпЛА між Петропавлівкою та Шахтарським" - беремо перше місто
        bpla_mizh_match = re.match(r'^[🛵🛸\s]*БпЛА\s+між\s+(\S+)\s+та\s+', line, re.IGNORECASE)
        if bpla_mizh_match:
            city = bpla_mizh_match.group(1).strip()
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            # Використовуємо current_region або геокодер
            region = current_region
            if not region:
                region = CITY_TO_REGION.get(city, None)
            if not region:
                region = await get_region_by_city(city)
            if region:
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
            continue
        
        # Формат: "Акустично шахед між Кременчуком та Горішніми Плавнями" - беремо перше місто
        akustychno_match = re.match(r'^[Аа]кустично\s+шахед\s+(?:між|біля|в районі)\s+(\S+)(?:\s+та\s+.+)?$', line, re.IGNORECASE)
        if akustychno_match and current_region:
            city = akustychno_match.group(1).strip()
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            msg = f"БПЛА {city} ({current_region})"
            messages.append(msg)
            continue
        
        # Формат ПС: "Харківщина: БПЛА невизначного типу біля Золочева" - Область: БПЛА ... біля Міста
        ps_region_bilya_match = re.match(r'^[🛵🛸\s]*(\S+):\s*(?:БпЛА|БПЛА)\s+.+?\s+біля\s+(\S+)\.?\s*$', line, re.IGNORECASE)
        if ps_region_bilya_match:
            short_region = ps_region_bilya_match.group(1).strip()
            city = ps_region_bilya_match.group(2).strip().rstrip('.')
            region = REGION_MAP.get(short_region, None)
            if region:
                city = fix_city_case(city)
                city = city[0].upper() + city[1:] if city else city
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
            continue
        
        # Формат ПС: "🛵 Чернігівщина: БпЛА в напрямку н.п. Березна, Ніжин, Борзна."
        # Область: БпЛА в напрямку н.п. Місто1, Місто2 - беремо тільки ПЕРШЕ місто
        ps_region_np_match = re.match(r'^[🛵🛸\s]*(\S+):\s*БпЛА\s+в\s+напрямку\s+(?:н\.п\.?\s*)?(.+?)(?:\s+з[іи]?\s+.+)?[\.;]?$', line, re.IGNORECASE)
        if ps_region_np_match:
            short_region = ps_region_np_match.group(1).strip()
            cities_str = ps_region_np_match.group(2).strip()
            region = REGION_MAP.get(short_region, None)
            if region:
                # Розділяємо міста по , та / і беремо ТІЛЬКИ ПЕРШЕ
                cities_str = cities_str.replace('/', ',')
                cities = [c.strip().rstrip('.;') for c in cities_str.split(',') if c.strip()]
                if cities:
                    city = cities[0]  # Беремо тільки перше місто
                    city = fix_city_case(city)
                    city = city[0].upper() + city[1:] if city else city
                    message = f"БПЛА {city} ({region})"
                    messages.append(message)
                continue
        
        # Формат ПС: "Житомирщина: 1 БпЛА в районі Малина"
        ps_region_v_rayoni_match = re.match(r'^[🛵🛸\s]*(\S+):\s*(\d+)\s*(?:БпЛА|БПЛА)\s+в\s+район[іу]\s+(.+?)\.?$', line, re.IGNORECASE)
        if ps_region_v_rayoni_match:
            short_region = ps_region_v_rayoni_match.group(1).strip()
            city = ps_region_v_rayoni_match.group(3).strip().rstrip('.')
            region = REGION_MAP.get(short_region, None)
            if region:
                city = fix_city_case(city)
                city = city[0].upper() + city[1:] if city else city
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
                continue
        
        # Формат ПС: "🛵 Житомирщина: БпЛА курсом на Коростень зі сходу." (1 БпЛА)
        ps_region_kursom_match = re.match(r'^[🛵🛸\s]*(\S+):\s*БпЛА\s+курсом\s+на\s+(.+?)(?:\s+з[іи]?\s+.+)?\.?$', line, re.IGNORECASE)
        if ps_region_kursom_match:
            short_region = ps_region_kursom_match.group(1).strip()
            city = ps_region_kursom_match.group(2).strip().rstrip('.')
            region = REGION_MAP.get(short_region, None)
            if region:
                city = fix_city_case(city)
                city = city[0].upper() + city[1:] if city else city
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
                continue
        
        # Формат ПС: "Nх БпЛА курсом на Місто" (з кількістю і current_region)
        bpla_qty_kursom_match = re.match(r'^[🛵🛸\s]*(\d+)\s*х?\s*БпЛА\s+курсом\s+на\s+(.+?)(?:\s+з[іи]?\s+.+)?\.?\s*$', line, re.IGNORECASE)
        if bpla_qty_kursom_match:
            city = bpla_qty_kursom_match.group(2).strip().rstrip('.')
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            # Використовуємо current_region або геокодер
            region = current_region
            if not region:
                region = CITY_TO_REGION.get(city, None)
            if not region:
                region = await get_region_by_city(city)
            if region:
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
            continue
        
        # Формат ПС: "БпЛА курсом на Місто" (без кількості, з current_region)
        bpla_kursom_current_region_match = re.match(r'^[🛵🛸\s]*БпЛА\s+курсом\s+на\s+(.+?)(?:\s+з[іи]?\s+.+)?\.?\s*$', line, re.IGNORECASE)
        if bpla_kursom_current_region_match:
            city = bpla_kursom_current_region_match.group(1).strip().rstrip('.')
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            # Використовуємо current_region або геокодер
            region = current_region
            if not region:
                region = CITY_TO_REGION.get(city, None)
            if not region:
                region = await get_region_by_city(city)
            if region:
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
            continue
        
        # Формат ПС: "🛵 БпЛА на сході Дніпропетровщини повз Шахтарське курсом на захід."
        ps_na_storoni_povz_match = re.match(r'^[🛵🛸\s]*БпЛА\s+на\s+(?:сході|заході|півночі|півдні)\s+(\S+)\s+повз\s+(\S+)\s+курсом.*$', line, re.IGNORECASE)
        if ps_na_storoni_povz_match:
            short_region = ps_na_storoni_povz_match.group(1).strip()
            city = ps_na_storoni_povz_match.group(2).strip().rstrip('.,;')
            region = REGION_MAP.get(short_region, None)
            if region:
                city = fix_city_case(city)
                city = city[0].upper() + city[1:] if city else city
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
                continue
        
        # Формат ПС: "🛵 БпЛА курсом на/повз Миколаїв з південного заходу."
        ps_kursom_na_match = re.match(r'^[🛵🛸\s]*БпЛА\s+курсом\s+(?:на/повз|на|повз)\s+(.+?)(?:\s+з[іи]?\s+.+)?\.?$', line, re.IGNORECASE)
        if ps_kursom_na_match:
            city = ps_kursom_na_match.group(1).strip().rstrip('.')
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            region = CITY_TO_REGION.get(city, None)
            if not region:
                region = await get_region_by_city(city)
            if region:
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
                continue
        
        # Формат ПС: "🛵 БпЛА з півночі курсом на Харків."
        ps_z_kursom_match = re.match(r'^[🛵🛸\s]*БпЛА\s+з\s+\S+\s+курсом\s+на\s+(.+?)\.?$', line, re.IGNORECASE)
        if ps_z_kursom_match:
            city = ps_z_kursom_match.group(1).strip().rstrip('.')
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            region = CITY_TO_REGION.get(city, None)
            if not region:
                region = await get_region_by_city(city)
            if region:
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
                continue
        
        # Формат ПС: "🛵 БпЛА на Донеччині курсом на Харківщину (Лозівський район)."
        ps_na_oblast_rayon_match = re.match(r'^[🛵🛸\s]*БпЛА\s+на\s+\S+\s+курсом\s+на\s+(\S+)\s*\((.+?)\s*район\)', line, re.IGNORECASE)
        if ps_na_oblast_rayon_match:
            short_region = ps_na_oblast_rayon_match.group(1).strip()
            rayon = ps_na_oblast_rayon_match.group(2).strip()
            region = REGION_MAP.get(short_region, None)
            if region:
                msg = f"БПЛА {rayon} ({region})"
                messages.append(msg)
                continue
        
        # Формат ПС: "🛵 БпЛА на півночі Чернігівщини курсом на Сновськ."
        ps_na_pivnochi_match = re.match(r'^[🛵🛸\s]*БпЛА\s+на\s+(?:півночі|півдні|заході|сході)\s+(\S+)\s+курсом\s+на\s+(.+?)\.?$', line, re.IGNORECASE)
        if ps_na_pivnochi_match:
            short_region = ps_na_pivnochi_match.group(1).strip()
            city = ps_na_pivnochi_match.group(2).strip().rstrip('.')
            region = REGION_MAP.get(short_region, None)
            if region:
                city = fix_city_case(city)
                city = city[0].upper() + city[1:] if city else city
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
                continue
        
        # Формат ПС: "🛵 БпЛА повз Седнів курсом на Чернігів."
        ps_povz_kursom_match = re.match(r'^[🛵🛸\s]*БпЛА\s+повз\s+\S+\s+курсом\s+на\s+(.+?)\.?$', line, re.IGNORECASE)
        if ps_povz_kursom_match:
            city = ps_povz_kursom_match.group(1).strip().rstrip('.')
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            region = CITY_TO_REGION.get(city, None)
            if not region:
                region = await get_region_by_city(city)
            if region:
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
                continue
        
        # Формат ПС: "🛵Харківщина: БпЛА повз Ізюм на сході південно-західним курсом."
        ps_region_povz_match = re.match(r'^[🛵🛸\s]*(\S+):\s*БпЛА\s+повз\s+(\S+).*$', line, re.IGNORECASE)
        if ps_region_povz_match:
            short_region = ps_region_povz_match.group(1).strip()
            city = ps_region_povz_match.group(2).strip().rstrip('.,;')
            region = REGION_MAP.get(short_region, None)
            if region:
                city = fix_city_case(city)
                city = city[0].upper() + city[1:] if city else city
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
                continue
        
        # Формат ПС: "🛵 Дніпропетровщина: БпЛА на півночі Павлограда, курс - західний"
        ps_region_na_pivnochi_match = re.match(r'^[🛵🛸\s]*(\S+):\s*БпЛА\s+на\s+(?:півночі|півдні|заході|сході)\s+(\S+?)(?:,|\s+курс).*$', line, re.IGNORECASE)
        if ps_region_na_pivnochi_match:
            short_region = ps_region_na_pivnochi_match.group(1).strip()
            city = ps_region_na_pivnochi_match.group(2).strip().rstrip('.,;')
            region = REGION_MAP.get(short_region, None)
            if region:
                city = fix_city_case(city)
                city = city[0].upper() + city[1:] if city else city
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
                continue
        
        # Формат ПС: "🛵 БпЛА на/повз Очаків на Миколаївщину"
        ps_na_povz_na_oblast_match = re.match(r'^[🛵🛸\s]*БпЛА\s+(?:на/повз|на|повз)\s+(\S+)\s+на\s+(\S+)(?:\s+з.+)?\.?$', line, re.IGNORECASE)
        if ps_na_povz_na_oblast_match:
            city = ps_na_povz_na_oblast_match.group(1).strip().rstrip('.,;')
            short_region = ps_na_povz_na_oblast_match.group(2).strip()
            region = REGION_MAP.get(short_region, None)
            if region:
                city = fix_city_case(city)
                city = city[0].upper() + city[1:] if city else city
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
                continue
        
        # Формат ПС: "🛵 БпЛА на Харківщині в напрямку н.п.Великий Бурлук" або "🛵 БпЛА на Миколаївщині в напрямку Снігурівки"
        ps_na_oblasti_v_napryamku_match = re.match(r'^[🛵🛸\s]*БпЛА\s+на\s+(\S+)\s+в\s+напрямку\s+(?:н\.п\.?\s*)?(.+?)(?:\s+з[іи]?\s+.+)?\.?$', line, re.IGNORECASE)
        if ps_na_oblasti_v_napryamku_match:
            short_region = ps_na_oblasti_v_napryamku_match.group(1).strip()
            city = ps_na_oblasti_v_napryamku_match.group(2).strip().rstrip('.')
            region = REGION_MAP.get(short_region, None)
            if region:
                city = fix_city_case(city)
                city = city[0].upper() + city[1:] if city else city
                message = f"БПЛА {city} ({region})"
                messages.append(message)
                continue
        
        # Формат: "🧨Загроза застосування балістичного озброєння" - балістична загроза
        balistyka_match = re.search(r'загроза\s+(?:застосування\s+)?балістич', line, re.IGNORECASE)
        if balistyka_match:
            msg = "Загроза балістики!"
            messages.append(msg)
            continue
        
        # Формат: "⚪️Відбій загрози застосування балістичного озброєння" - відбій балістичної загрози (пропускаємо)
        vidbiy_balistyka_match = re.search(r'відбій\s+загроз[иі]\s+(?:застосування\s+)?балістич', line, re.IGNORECASE)
        if vidbiy_balistyka_match:
            continue
        
        # Формат: "� Ракета курсом на Київ" або "Крилата ракета на Харків"
        raketa_match = re.match(r'^[🚀🔴⚠️❗️\s]*(?:крилат[аі]?\s+)?ракет[аи]?\s+(?:курсом\s+)?(?:на|в напрямку)\s+(.+?)(?:\s+з.+)?[!\.]*$', line, re.IGNORECASE)
        if raketa_match:
            city = raketa_match.group(1).strip().rstrip('.')
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            region = CITY_TO_REGION.get(city, None)
            if not region:
                region = await get_region_by_city(city)
            if region:
                msg = f"Ракета {city} ({region})"
                messages.append(msg)
                continue
        
        # Формат: "�💣 Краматорський район (Донецька обл.)" - КАБи по району (тільки з emoji 💣)
        if '💣' in line:
            kab_rayon_match = re.match(r'^[💣\s]*(.+?)\s+район\s*\((.+?обл\.?)\)', line, re.IGNORECASE)
            if kab_rayon_match:
                rayon = kab_rayon_match.group(1).strip()
                region = kab_rayon_match.group(2).strip()
                rayon = rayon[0].upper() + rayon[1:] if rayon else rayon
                region = region[0].upper() + region[1:] if region else region
                if not region.endswith('.'):
                    region = region + '.'
                msg = f"КАБ {rayon} ({region})"
                messages.append(msg)
                continue
        
        # Формат: "⚠️2х Шахеди на Запоріжжя!" - Шахеди/шахед на місто
        shahedy_na_match = re.match(r'^[⚠️❗️🔴\s]*(\d+)\s*х?\s*(?:Шахед[иі]?|шахед[иі]?)\s+на\s+(.+?)[!\.]*$', line, re.IGNORECASE)
        if shahedy_na_match:
            city = shahedy_na_match.group(2).strip()
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            region = CITY_TO_REGION.get(city, None)
            if not region:
                region = await get_region_by_city(city)
            if region:
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
                continue
        
        # Формат ПС: "🛵 БпЛА з Миколаївщини курсом на Одещину (вектор - Доброслав)"
        ps_z_oblasti_vektor_match = re.match(r'^[🛵🛸\s]*(?:Група\s+)?БпЛА\s+(?:з\s+\S+\s+)?курсом\s+на\s+(\S+)(?:\s+з.+?)?\s*\(вектор\s*[-–—]\s*(.+?)\)', line, re.IGNORECASE)
        if ps_z_oblasti_vektor_match:
            short_region = ps_z_oblasti_vektor_match.group(1).strip()
            city = ps_z_oblasti_vektor_match.group(2).strip().rstrip('.')
            region = REGION_MAP.get(short_region, None)
            if region:
                city = fix_city_case(city)
                city = city[0].upper() + city[1:] if city else city
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
                continue
        
        # Формат ПС: "🛵БпЛА на Нікопольський р-н Дніпропетровщини"
        ps_na_rayon_oblasti_match = re.match(r'^[🛵🛸\s]*БпЛА\s+на\s+(\S+)\s+р-н\s+(\S+)(?:\s+з.+)?\.?$', line, re.IGNORECASE)
        if ps_na_rayon_oblasti_match:
            rayon = ps_na_rayon_oblasti_match.group(1).strip()
            short_region = ps_na_rayon_oblasti_match.group(2).strip()
            region = REGION_MAP.get(short_region, None)
            if region:
                # Виправляємо відмінок району (Нікопольський -> Нікопольський)
                msg = f"БПЛА {rayon} ({region})"
                messages.append(msg)
                continue
        
        # Формат ПС: "🛵 Дніпропетровщина: БпЛА в напрямку Зеленодольська та Кривого Рогу"
        ps_region_ta_match = re.match(r'^[🛵🛸\s]*(\S+):\s*БпЛА\s+в\s+напрямку\s+(.+?)\s+та\s+(.+?)(?:\s+з[іи]?\s+.+)?\.?$', line, re.IGNORECASE)
        if ps_region_ta_match:
            short_region = ps_region_ta_match.group(1).strip()
            city1 = ps_region_ta_match.group(2).strip().rstrip('.,;')
            city2 = ps_region_ta_match.group(3).strip().rstrip('.,;')
            region = REGION_MAP.get(short_region, None)
            if region:
                for city in [city1, city2]:
                    city = fix_city_case(city)
                    city = city[0].upper() + city[1:] if city else city
                    msg = f"БПЛА {city} ({region})"
                    messages.append(msg)
                continue
        
        # Формат ПС: "🛵Змінив курс на Ріпки." - використовуємо current_region
        ps_zminiv_kurs_match = re.match(r'^[🛵🛸\s]*Змінив\s+курс\s+на\s+(.+?)\.?$', line, re.IGNORECASE)
        if ps_zminiv_kurs_match:
            city = ps_zminiv_kurs_match.group(1).strip().rstrip('.')
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            region = current_region
            if not region:
                region = CITY_TO_REGION.get(city, None)
            if not region:
                region = await get_region_by_city(city)
            if region:
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
                continue
        
        # Формат 0: "бпла місто по межі (область) загроза..." - з "по межі" або подібними фразами
        # Наприклад: "бпла брусилів по межі (житомирська обл.) загроза застосування бпла."
        po_mezhi_match = re.match(r'^[💥🛸🛵⚠️❗️🔴👁️\s]*(бпла|БпЛА|БПЛА)?\s*(\d*х?\s*)?(.+?)\s+(?:по межі|на межі|біля межі|в напрямку|в районі)\s*\((.+?обл\.?)\)', line, re.IGNORECASE)
        if po_mezhi_match:
            quantity = po_mezhi_match.group(2) or ''
            quantity = quantity.strip()
            if quantity and not quantity.endswith('х'):
                quantity = quantity + 'х'
            if quantity:
                quantity = quantity + ' '
            city = po_mezhi_match.group(3).strip()
            # Видаляємо "бпла" з назви міста якщо залишилось
            city = re.sub(r'^(бпла|БпЛА|БПЛА)\s*', '', city, flags=re.IGNORECASE).strip()
            # Видаляємо "на" якщо залишилось
            city = re.sub(r'^на\s*$', '', city, flags=re.IGNORECASE).strip()
            # Пропускаємо якщо місто порожнє або занадто коротке
            if not city or len(city) < 2:
                continue
            # Виправляємо відмінок
            city = fix_city_case(city)
            # Capitalize першу літеру міста
            city = city[0].upper() + city[1:] if city else city
            region = po_mezhi_match.group(4).strip()
            # Capitalize область
            region = region[0].upper() + region[1:] if region else region
            if not region.endswith('.'):
                region = region + '.'
            
            msg = f"БПЛА {city} ({region})"
            messages.append(msg)
            continue
        
        # Формат 0.5: "БПЛА з Області курсом на Область (Район район обл.)" 
        # Наприклад: "БПЛА з Чернігівщини курсом на Київщину (Вишгородський район обл.)"
        # Або: "БПЛА Донеччині курсом на Харківщину (Лозівський район обл.)"
        z_oblasti_rayon_match = re.match(r'^[💥🛸🛵⚠️❗️🔴👁️\s]*(\d*х?\s*)?(бпла|БпЛА|БПЛА)\s+(?:з\s+)?\S+\s+курсом\s+на\s+(\S+)\s*\((.+?)\s+район\s*обл\.?\)', line, re.IGNORECASE)
        if z_oblasti_rayon_match:
            quantity = z_oblasti_rayon_match.group(1) or ''
            quantity = quantity.strip()
            if quantity and not quantity.endswith('х'):
                quantity = quantity + 'х'
            if quantity:
                quantity = quantity + ' '
            short_region = z_oblasti_rayon_match.group(3).strip()
            rayon = z_oblasti_rayon_match.group(4).strip()
            # Конвертуємо скорочену назву області в повну
            region = REGION_MAP.get(short_region, None)
            # Якщо не знайшли, пробуємо без закінчення (Київщину -> Київщина)
            if not region:
                short_region_fixed = fix_city_case(short_region)
                region = REGION_MAP.get(short_region_fixed, short_region_fixed + ' обл.')
            
            message = f"{quantity}БПЛА {rayon} район ({region})"
            messages.append(message)
            continue
        
        # Формат: "7х БпЛА в Покровському районі (Київська обл.)" - кількість + район + область
        v_rayoni_match = re.match(r'^[💥🛸🛵⚠️❗️🔴👁️\s]*(\d+)\s*х?\s*(?:БпЛА|БПЛА)?\s*(?:в|у)\s+(.+?)\s+район[іу]?\s*\((.+?обл\.?)\)', line, re.IGNORECASE)
        if v_rayoni_match:
            rayon = v_rayoni_match.group(2).strip()
            region = v_rayoni_match.group(3).strip()
            # Capitalize
            rayon = rayon[0].upper() + rayon[1:] if rayon else rayon
            region = region[0].upper() + region[1:] if region else region
            if not region.endswith('.'):
                region = region + '.'
            msg = f"БПЛА {rayon} ({region})"
            messages.append(msg)
            continue
        
        # Формат: "БпЛА в Покровському районі (Київська обл.)" - без кількості
        v_rayoni_no_qty_match = re.match(r'^[💥🛸🛵⚠️❗️🔴👁️\s]*(?:БпЛА|БПЛА)\s+(?:в|у)\s+(.+?)\s+район[іу]?\s*\((.+?обл\.?)\)', line, re.IGNORECASE)
        if v_rayoni_no_qty_match:
            rayon = v_rayoni_no_qty_match.group(1).strip()
            region = v_rayoni_no_qty_match.group(2).strip()
            # Capitalize
            rayon = rayon[0].upper() + rayon[1:] if rayon else rayon
            region = region[0].upper() + region[1:] if region else region
            if not region.endswith('.'):
                region = region + '.'
            msg = f"БПЛА {rayon} ({region})"
            messages.append(msg)
            continue
        
        # Формат 1: "💥 Марганець (Дніпропетровська обл.)" або "🛸 Чернігів (Чернігівська обл.)"
        # Готові повідомлення з містом та областю (може бути текст після області)
        ready_match = re.match(r'^[💥🛸🛵⚠️❗️🔴👁️🚀✈️\s]*(.+?)\s*\((.+?обл\.?)\)', line, re.IGNORECASE)
        if ready_match:
            # ВАЖЛИВО: Перевіряємо чи наступний рядок містить "вибухи" - тоді пропускаємо (вже оброблено раніше)
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if 'вибух' in next_line.lower() or 'вибух' in line.lower():
                continue  # Пропускаємо - це повідомлення про вибухи, оброблено вище
            
            # ВАЖЛИВО: Перевіряємо тип загрози ДО видалення emoji
            # 🚀 = Ракета, інші emoji (🛸, 🛵, 💥) = БПЛА
            threat_type = "Ракета" if '🚀' in line else "БПЛА"
            
            city = ready_match.group(1).strip()
            # Видаляємо emoji з назви міста
            city = re.sub(r'^[💥🛸🛵⚠️❗️🔴👁️🚀✈️\*\s]+', '', city).strip()
            city = re.sub(r'[🚀💥🛸🛵⚠️❗️🔴👁️✈️]+', '', city).strip()  # Видаляємо emoji в будь-якому місці
            city = re.sub(r'[\*]+', '', city).strip()
            # Видаляємо "бпла" з назви міста
            city = re.sub(r'^(бпла|БпЛА|БПЛА)\s*', '', city, flags=re.IGNORECASE).strip()
            # Видаляємо кількість на початку (7х, 3х тощо)
            city = re.sub(r'^\d+\s*х?\s*', '', city).strip()
            # Видаляємо повторне "бпла" після кількості
            city = re.sub(r'^(бпла|БпЛА|БПЛА)\s*', '', city, flags=re.IGNORECASE).strip()
            
            # ВАЖЛИВО: Якщо є "курсом на X" - беремо X як кінцевий пункт
            kursom_match = re.search(r'курсом\s+на\s+(.+)$', city, re.IGNORECASE)
            if kursom_match:
                city = kursom_match.group(1).strip()
            
            # Видаляємо "Околиці" - залишаємо тільки місто
            city = re.sub(r'^[Оо]колиц[іи]\s+', '', city, flags=re.IGNORECASE).strip()
            
            # Видаляємо "район" / "р" в кінці
            city = re.sub(r'\s+район\s*$', '', city, flags=re.IGNORECASE).strip()
            city = re.sub(r'\s+р\s*$', '', city, flags=re.IGNORECASE).strip()
            
            # Видаляємо "Ст." на початку (Ст.Салтів -> Салтів)
            city = re.sub(r'^Ст\.?\s*', '', city, flags=re.IGNORECASE).strip()
            
            # ВАЖЛИВО: Якщо є "Місто та Місто2" або "Місто1 та Місто2" - беремо тільки перше місто
            if ' та ' in city:
                city = city.split(' та ')[0].strip()
            
            # Видаляємо "з Області" конструкцію (напр. "Долинська з Дніпропетровщини" -> "Долинська")
            city = re.sub(r'\s+з\s+(?:Сумщини|Чернігівщини|Полтавщини|Черкащини|Київщини|Харківщини|Дніпропетровщини|Миколаївщини|Одещини|Херсонщини|Запоріжжя|Донеччини|Луганщини|Житомирщини|Вінниччини|Хмельниччини|Рівненщини|Волині|Львівщини|Тернопільщини|Івано-Франківщини|Закарпаття|Кіровоградщини)\s*$', '', city, flags=re.IGNORECASE).strip()
            
            # Видаляємо "в районі", "по межі", "у напрямку", "в напрямку" тощо на початку
            city = re.sub(r'^(\d*х?\s*)?(в районі|по межі|на межі|біля межі|[уів]\s+напрямку|на)\s+', '', city, flags=re.IGNORECASE).strip()
            # Видаляємо "з моря", "з моря(~15х)", "з області", "зі сходу" тощо в кінці
            city = re.sub(r'\s+з[іи]?\s+\S+(?:\([^)]*\))?$', '', city, flags=re.IGNORECASE).strip()
            # Видаляємо "➡️ курсом на ...", "курсом на ..." в кінці (якщо ще залишилось)
            city = re.sub(r'\s*➡️?\s*курсом\s+на\s+.+$', '', city, flags=re.IGNORECASE).strip()
            
            # Пропускаємо якщо це формат з "район" в назві (наприклад "Харківський район" чи "в районі")
            if re.search(r'район', city, re.IGNORECASE):
                continue
            
            # Пропускаємо якщо "місто" насправді є назвою області
            is_region_name = False
            for region_key in REGION_MAP.keys():
                if city.lower() == region_key.lower() or city.lower().rstrip('аиуіїею') == region_key.lower().rstrip('аиуіїею'):
                    is_region_name = True
                    break
            if is_region_name:
                continue
            # Пропускаємо якщо місто містить дієслова або фрази (не назва міста)
            skip_words = ['кружляють', 'кружляє', 'летить', 'летять', 'рухається', 'рухаються', 
                         'курсом', 'на межі', 'по межі', 'в напрямку', 'у напрямку', 'повз',
                         'змінив', 'змінює', 'зайшов', 'зайшли', 'вийшов', 'вийшли']
            should_skip = False
            for skip_word in skip_words:
                if skip_word.lower() in city.lower():
                    should_skip = True
                    break
            if should_skip or len(city) < 2:
                continue
            # Виправляємо відмінок
            city = fix_city_case(city)
            # Capitalize першу літеру міста
            city = city[0].upper() + city[1:] if city else city
            region = ready_match.group(2).strip()
            # Видаляємо "н.п." з області
            region = re.sub(r'^н\.п\.?\s*', '', region, flags=re.IGNORECASE).strip()
            # Capitalize область
            region = region[0].upper() + region[1:] if region else region
            if not region.endswith('.'):
                region = region + '.'
            
            msg = f"{threat_type} {city} ({region})"
            messages.append(msg)
            continue
        
        # Формат 2: "🛸 Шахед курсом на Південноукраїнськ (Миколаївщина)" або "🛸 3 Шахеда курсом на Запоріжжя (Дніпропетровщина)"
        course_match = re.match(r'^[💥🛸🛵⚠️❗️🔴👁️\s]*(\d*)\s*[Шш]ахед[іиіва]*\s+курсом\s+на\s+(.+?)\s*\((.+?)\)', line, re.IGNORECASE)
        if course_match:
            city = course_match.group(2).strip()
            short_region = course_match.group(3).strip()
            
            # Конвертуємо скорочену назву області в повну
            region = REGION_MAP.get(short_region, short_region + ' обл.')
            
            msg = f"БПЛА {city} ({region})"
            messages.append(msg)
            continue
        
        # Формат 3: "⚠️2х БпЛА на Шостку (Сумщина)" - місто і скорочена область в дужках
        short_region_match = re.match(r'^[💥🛸🛵⚠️❗️🔴👁️\s]*(\d*х?\s*)?(БпЛА|БПЛА|шахед[іиів]*)\s+(?:на\s+)?(.+?)\s*\((.+?)\)', line, re.IGNORECASE)
        if short_region_match:
            city = short_region_match.group(3).strip()
            short_region = short_region_match.group(4).strip()
            
            # Конвертуємо скорочену назву області в повну
            region = REGION_MAP.get(short_region, short_region + ' обл.')
            
            msg = f"БПЛА {city} ({region})"
            messages.append(msg)
            continue
        
        # Формат 3: "⚠️8х БпЛА повз Кривий ріг на Кіровоградщину" - місто і область в тексті
        direction_match = re.match(r'^[💥🛸🛵⚠️❗️🔴👁️\s]*(\d*х?\s*)?(БпЛА|БПЛА|шахед[іиів]*)\s+(?:повз|на|курсом на)\s+(.+?)\s+(?:на|в|до)\s+(.+?)$', line, re.IGNORECASE)
        if direction_match:
            city = direction_match.group(3).strip()
            short_region = direction_match.group(4).strip()
            
            # Конвертуємо скорочену назву області в повну
            region = REGION_MAP.get(short_region, None)
            if not region and city in CITY_TO_REGION:
                region = CITY_TO_REGION[city]
            
            if region:
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
            continue
        
        # Формат: 🛵5х Шахедів на Кривий Ріг! або 🛵Вже 5х Шахедів на місто!
        shahedy_na_match = re.match(r'^[🛵🛸💥⚠️❗️\s]*(?:Вже\s+)?(\d+)х?\s*[Шш]ахед[іиіва]*\s+на\s+(.+?)!?$', line, re.IGNORECASE)
        if shahedy_na_match:
            city = await split_cities(shahedy_na_match.group(2).strip().rstrip('!'))
            region = current_region
            if not region:
                region = await get_region_by_city(city)
            if region:
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
            continue
        
        # Перевіряємо чи це регіон (📡Харківщина: або просто Харківщина: або ✈️Дніпропетровщина:)
        is_region = False
        region_header_match = re.match(r'^[📡⚠️🔴✈️\s]*([^:]+):', line)
        if region_header_match:
            potential_region = region_header_match.group(1).strip()
            for region_key in REGION_MAP.keys():
                if region_key in potential_region:
                    current_region = REGION_MAP[region_key]
                    is_region = True
                    break
            # Спеціальний випадок для "Запорізька область"
            if 'Запорізьк' in potential_region:
                current_region = 'Запорізька обл.'
                is_region = True
        
        if is_region:
            continue
        
        # Формат: ✈️ БПЛA "Молнія"→Миколаїв/р-н або ✈️ БПЛА "Герань"→Київ
        bpla_type_match = re.match(r'^[✈️🛸🛵\s]*(БПЛА?|БпЛА)\s*["\«]?([^"»\→]+)["\»]?\s*[→➡️]\s*(.+?)(?:/(?:р-н|район|околиц[іи]))?\s*$', line, re.IGNORECASE)
        if bpla_type_match:
            bpla_type = bpla_type_match.group(2).strip()
            city = bpla_type_match.group(3).strip()
            city = city.rstrip('.')
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            region = current_region
            if not region:
                region = CITY_TO_REGION.get(city, None)
            if not region:
                region = await get_region_by_city(city)
            if region:
                message = f"БПЛА \"{bpla_type}\" {city} ({region})"
                messages.append(message)
            continue
        
        # Формат: →Місто1/Місто2 або →Місто1/Місто2(Nх) або →Місто/р-н
        # Приклади: →Охтирка/Харківщина(3х) → "БПЛА Охтирка (Сумська обл.)" (Харківщина = напрямок, ігноруємо)
        #           →Водолага/Коломак (3х) → "БПЛА Коломак (Харківська обл.)" (беремо кінцевий пункт)
        #           →Олександрія/р-н (2х) → "БПЛА Олександрія (Кіровоградська обл.)"
        #           →Дніпропетровщина (3х) → пропускаємо (це область, не місто)
        arrow_match = re.match(r'^[→➡️]\s*(.+?)\s*[\.;]?$', line)
        if arrow_match and current_region:
            content = arrow_match.group(1).strip()
            
            # Витягуємо кількість з дужок (7х), (3х) тощо - але НЕ додаємо до результату
            quantity_match = re.search(r'\((\d+)х?\)', content)
            if quantity_match:
                content = re.sub(r'\s*\(\d+х?\)', '', content)
            
            # Видаляємо крапки та крапки з комою в кінці
            content = content.rstrip('.;')
            
            # Перевіряємо чи весь content це назва області - тоді пропускаємо
            is_only_region = False
            for region_key in REGION_MAP.keys():
                if content.lower().strip() == region_key.lower() or content.lower().rstrip('аиуіїею') == region_key.lower().rstrip('аиуіїею'):
                    is_only_region = True
                    break
            if is_only_region:
                continue
            
            # Перевіряємо чи є / в рядку
            if '/' in content:
                parts = content.split('/')
                city1 = parts[0].strip()
                city2 = parts[1].strip() if len(parts) > 1 else ''
                
                # Перевіряємо що таке city2
                if city2.lower() in ['р-н', 'район', 'околиці', 'околиц']:
                    # →Олександрія/р-н → "БПЛА Олександрія (Область)"
                    city1 = fix_city_case(city1)
                    city1 = city1[0].upper() + city1[1:] if city1 else city1
                    message = f"БПЛА {city1} ({current_region})"
                    messages.append(message)
                elif city2 in REGION_MAP or any(rk.lower() in city2.lower() for rk in REGION_MAP.keys()):
                    # →Охтирка/Харківщина → city2 це область/напрямок, беремо тільки city1
                    city1 = fix_city_case(city1)
                    city1 = city1[0].upper() + city1[1:] if city1 else city1
                    message = f"БПЛА {city1} ({current_region})"
                    messages.append(message)
                else:
                    # →Водолага/Коломак → два міста, беремо КІНЦЕВИЙ пункт (city2)
                    city2 = fix_city_case(city2)
                    city2 = city2[0].upper() + city2[1:] if city2 else city2
                    message = f"БПЛА {city2} ({current_region})"
                    messages.append(message)
            else:
                # Просто одне місто: →Васильківка
                city = fix_city_case(content)
                city = city[0].upper() + city[1:] if city else city
                message = f"БПЛА {city} ({current_region})"
                messages.append(message)
            continue
        
        # Формат: 💥 Павлоград/околиці - ще вибухи. або 💥Коростень/р-н (Житомирщинa) - вибухи.
        explosion_match = re.match(r'^[💥🔥]\s*(.+?)(?:/(?:околиц[іи]|р-н|район))?\s*(?:\((.+?)\))?\s*[-–—]\s*(.+)$', line)
        if explosion_match:
            city = explosion_match.group(1).strip()
            region_in_parens = explosion_match.group(2)
            
            # Видаляємо зайве з назви міста
            city = city.rstrip('/')
            city = fix_city_case(city)
            city = city[0].upper() + city[1:] if city else city
            
            # Визначаємо область
            if region_in_parens:
                # Нормалізуємо (Житомирщинa -> Житомирщина)
                region_in_parens = region_in_parens.strip()
                region = REGION_MAP.get(region_in_parens, None)
                if not region:
                    # Пробуємо знайти схожу назву
                    for region_key in REGION_MAP.keys():
                        if region_key.lower()[:5] in region_in_parens.lower():
                            region = REGION_MAP[region_key]
                            break
                if not region:
                    region = current_region
            else:
                region = current_region
                if not region:
                    region = await get_region_by_city(city)
            
            if region:
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
            continue
        
        # Формат: ⚠️БпЛА курсом на Харків або ⚠️2х БпЛА курсом на Кривий Ріг або БпЛА курсом на Пʼятихатки
        bpla_kursom_match = re.match(r'^[⚠️❗️🔴\s]*(\d*х?\s*)?(БпЛА|БПЛА)\s+курсом\s+на\s+(.+?)\s*$', line, re.IGNORECASE)
        if bpla_kursom_match:
            city = await split_cities(bpla_kursom_match.group(3).strip())
            # Використовуємо current_region або геокодинг
            region = current_region
            if not region:
                region = await get_region_by_city(city)
            if region:
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
            continue
        
        # Формат: 3х БпЛА маневрують південніше Зеленодольська
        manevruyut_match = re.match(r'^[⚠️❗️🔴\s]*(\d*х?\s*)?(БпЛА|БПЛА)\s+маневрують\s+(?:південніше|північніше|західніше|східніше|біля|в районі)\s+(.+?)\s*$', line, re.IGNORECASE)
        if manevruyut_match:
            city = await split_cities(manevruyut_match.group(3).strip())
            region = current_region
            if not region:
                region = await get_region_by_city(city)
            if region:
                msg = f"БПЛА {city} ({region})"
                messages.append(msg)
            continue
        
        # Парсимо рядки з БпЛА/шахедами
        if any(keyword in line.lower() for keyword in ['бпла', 'шахед', 'шахід']):
            # Витягуємо кількість та текст
            # Формати: "2 шахеди на Чернігів", "2х БпЛА курсом на Київ", "БпЛА на Харків", "4 шахеди через Казанку в бік Кіровоградщини"
            
            # Спроба 1: "число + шахед/шахедів/шахеди + через + місто + в бік + область"
            match = re.match(r'(\d+)\s*(шахед[іиів]*|БпЛА|БПЛА)\s+через\s+(.+?)\s+в\s+бік\s+(.+)$', line, re.IGNORECASE)
            if match:
                city = match.group(3).strip()
                short_region = match.group(4).strip()
                region = REGION_MAP.get(short_region, current_region)
                if region:
                    msg = f"БПЛА {city} ({region})"
                    messages.append(msg)
                continue
            
            # Спроба 2: "число + шахед + кружляє біля/в районі + місто" (1 шахед кружляє біля Південноукраїнська)
            match = re.match(r'(\d+)\s*(шахед[іиів]*|БпЛА|БПЛА)\s+кружляє\s+(?:біля|в районі)\s+(.+)$', line, re.IGNORECASE)
            if match:
                city = await split_cities(match.group(3).strip())
                region = current_region
                if not region:
                    region = await get_region_by_city(city)
                if region:
                    msg = f"БПЛА {city} ({region})"
                    messages.append(msg)
                continue
            
            # Спроба 3: "число + шахед + з + область + на + місто" (1 шахед з Сумщини на Талалаївку)
            match = re.match(r'(\d+)\s*(шахед[іиів]*|БпЛА|БПЛА)\s+з\s+\S+\s+на\s+(.+)$', line, re.IGNORECASE)
            if match:
                city = await split_cities(match.group(3).strip())
                region = current_region
                if not region:
                    region = await get_region_by_city(city)
                if region:
                    msg = f"БПЛА {city} ({region})"
                    messages.append(msg)
                continue
            
            # Спроба 4: "число + шахед/шахедів/шахеди + на + місто" (1 шахед на Березнегувате)
            match = re.match(r'(\d+)\s*(шахед[іиів]*|БпЛА|БПЛА)\s+(?:курсом\s+)?на\s+(.+)$', line, re.IGNORECASE)
            if match:
                city = match.group(3).strip()
                # Видаляємо "с." на початку (с.Рівне -> Рівне)
                city = re.sub(r'^с\.', '', city).strip()
                city = await split_cities(city)
                region = current_region
                if not region:
                    region = await get_region_by_city(city)
                if region:
                    msg = f"БПЛА {city} ({region})"
                    messages.append(msg)
                continue
            
            # Спроба 4: "числох БпЛА на місто"
            match = re.match(r'(\d+)х?\s*(БпЛА|БПЛА)\s*(?:курсом\s+)?(?:на\s+)?(.+)$', line, re.IGNORECASE)
            if match:
                city = match.group(3).strip()
                city = re.sub(r'\s*курсом.*$', '', city)
                city = re.sub(r'\s*з\s+.*$', '', city)
                city = await split_cities(city.strip())
                region = current_region
                if not region:
                    region = await get_region_by_city(city)
                if city and region:
                    msg = f"БПЛА {city} ({region})"
                    messages.append(msg)
                continue
            
            # Спроба 5: "БпЛА на місто" (без числа)
            match = re.match(r'(БпЛА|БПЛА)\s*(?:курсом\s+)?(?:на\s+)?(.+)$', line, re.IGNORECASE)
            if match:
                city = match.group(2).strip()
                city = re.sub(r'\s*курсом.*$', '', city)
                city = re.sub(r'\s*з\s+.*$', '', city)
                city = await split_cities(city.strip())
                region = current_region
                if not region:
                    region = await get_region_by_city(city)
                if city and region:
                    msg = f"БПЛА {city} ({region})"
                    messages.append(msg)
                continue
    
    # Повертаємо знайдені повідомлення
    return messages


async def ensure_connected():
    """Перевірка та відновлення з'єднання"""
    if not client.is_connected():
        logger.info("🔄 Перепідключення до Telegram...")
        try:
            await client.connect()
            if await client.is_user_authorized():
                logger.info("✅ Перепідключено успішно")
                return True
            else:
                logger.error("❌ Сесія не авторизована")
                return False
        except Exception as e:
            logger.error(f"❌ Помилка перепідключення: {e}")
            return False
    return True


async def check_and_forward():
    """Перевірка нових повідомлень та пересилання"""
    
    # Перевіряємо з'єднання перед кожною перевіркою
    if not await ensure_connected():
        return
    forwarded_count = 0
    
    for channel in SOURCE_CHANNELS:
        channel = channel.strip()
        if not channel:
            continue
            
        try:
            entity = await client.get_entity(channel)
            
            # Отримуємо останнє повідомлення
            async for message in client.iter_messages(entity, limit=1):
                # Перевіряємо, чи вже пересилали це повідомлення
                if channel not in last_message_ids:
                    # Перший запуск - зберігаємо ID і пропускаємо
                    last_message_ids[channel] = message.id
                    logger.info(f"📌 {channel}: збережено початковий ID {message.id}")
                    continue
                
                if message.id > last_message_ids[channel]:
                    # Нове повідомлення!
                    logger.info(f"🆕 Нове повідомлення в @{channel}: ID {message.id}")
                    
                    # Розбиваємо повідомлення на окремі
                    split_messages = await parse_and_split_message(message.text)
                    
                    # Пропускаємо якщо немає валідних повідомлень
                    if not split_messages or (len(split_messages) == 1 and not split_messages[0]):
                        logger.info(f"⏭️ Пропущено повідомлення без конкретних локацій")
                        last_message_ids[channel] = message.id
                        continue
                    
                    # Пересилаємо кожне окреме повідомлення
                    try:
                        sent_count = 0
                        for split_msg in split_messages:
                            if not split_msg or not split_msg.strip():
                                continue
                            
                            # Перевіряємо на дублікат
                            if is_duplicate(split_msg):
                                continue
                                
                            if message.media:
                                # Якщо є медіа, відправляємо тільки з першим повідомленням
                                if split_msg == split_messages[0]:
                                    await client.send_message(
                                        TARGET_CHANNEL,
                                        split_msg,
                                        file=message.media
                                    )
                                else:
                                    await client.send_message(
                                        TARGET_CHANNEL,
                                        split_msg
                                    )
                            else:
                                await client.send_message(
                                    TARGET_CHANNEL,
                                    split_msg
                                )
                            
                            # Позначаємо як відправлене
                            mark_as_sent(split_msg)
                            sent_count += 1
                            
                            # Невелика затримка між повідомленнями
                            await asyncio.sleep(0.5)
                        
                        # Оновлюємо ID
                        last_message_ids[channel] = message.id
                        if sent_count > 0:
                            forwarded_count += 1
                            logger.info(f"✅ Переслано {sent_count} повідомлень з @{channel} в @{TARGET_CHANNEL}")
                        
                    except Exception as e:
                        logger.error(f"❌ Помилка пересилання з @{channel}: {e}")
                
        except Exception as e:
            logger.error(f"❌ Помилка перевірки @{channel}: {e}")
    
    if forwarded_count > 0:
        logger.info(f"📊 Переслано {forwarded_count} повідомлень")


async def main():
    """Головна функція"""
    
    logger.info("🚀 Запуск Channel Forwarder (Polling mode)...")
    
    # Підключення з session string (без phone)
    await client.connect()
    
    if not await client.is_user_authorized():
        logger.error("❌ Сесія не авторизована! Перевірте TELEGRAM_SESSION")
        return
    
    me = await client.get_me()
    logger.info(f"✅ Авторизовано: {me.first_name} ({me.phone})")
    
    # Перевірка цільового каналу
    try:
        target = await client.get_entity(TARGET_CHANNEL)
        logger.info(f"✅ Цільовий канал: {target.title} (@{TARGET_CHANNEL})")
    except Exception as e:
        logger.error(f"❌ Не вдалося знайти @{TARGET_CHANNEL}: {e}")
        return
    
    # Перевірка вихідних каналів
    valid_sources = []
    for channel in SOURCE_CHANNELS:
        channel = channel.strip()
        if not channel:
            continue
        try:
            entity = await client.get_entity(channel)
            valid_sources.append(channel)
            logger.info(f"✅ Вихідний канал: {entity.title} (@{channel})")
        except Exception as e:
            logger.warning(f"⚠️ Не вдалося знайти @{channel}: {e}")
    
    if not valid_sources:
        logger.error("❌ Жодного каналу не знайдено!")
        return
    
    total_channels = len(valid_sources)
    logger.info(f"\n📊 Моніторю {total_channels} каналів")
    logger.info(f"⏱️  Перевірка кожні {POLL_INTERVAL} секунд")
    logger.info(f"🎯 Пересилання в @{TARGET_CHANNEL}\n")
    
    # Головний цикл опитування
    while True:
        try:
            await check_and_forward()
            await asyncio.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"❌ Помилка в циклі: {e}")
            await asyncio.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n\n⏹️ Бот зупинено")
    except Exception as e:
        logger.error(f"\n\n❌ Критична помилка: {e}")
        raise
