#!/usr/bin/env python3
"""
Channel Forwarder з polling (опитування)
Перевіряє канали кожні 30 секунд
Оптимізовано для Render.com
"""

import asyncio
import logging
import re
from telethon import TelegramClient
from telethon.sessions import StringSession
import os
import sys

logging.basicConfig(
    format='[%(levelname)s/%(asctime)s] %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфігурація з environment variables
API_ID = os.getenv('TELEGRAM_API_ID')
API_HASH = os.getenv('TELEGRAM_API_HASH')
STRING_SESSION = os.getenv('TELEGRAM_SESSION')

SOURCE_CHANNELS = os.getenv('SOURCE_CHANNELS', 'UkraineAlarmSignal,kpszsu,war_monitor,napramok,raketa_trevoga,ukrainsiypposhnik').split(',')
TARGET_CHANNEL = os.getenv('TARGET_CHANNEL', 'mapstransler')

# Інтервал опитування (секунди)
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '30'))

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

# Клієнт з StringSession для Render
client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

# Мапінг регіонів на українську мову
REGION_MAP = {
    'Сумщина': 'Сумська обл.',
    'Чернігівщина': 'Чернігівська обл.',
    'Полтавщина': 'Полтавська обл.',
    'Черкащина': 'Черкаська обл.',
    'Київщина': 'Київська обл.',
    'Харківщина': 'Харківська обл.',
    'Дніпропетровщина': 'Дніпропетровська обл.',
    'Миколаївщина': 'Миколаївська обл.',
    'Одещина': 'Одеська обл.',
    'Херсонщина': 'Херсонська обл.',
    'Запорізька': 'Запорізька обл.',
    'Донеччина': 'Донецька обл.',
    'Луганщина': 'Луганська обл.',
    'Житомирщина': 'Житомирська обл.',
    'Вінниччина': 'Вінницька обл.',
    'Хмельниччина': 'Хмельницька обл.',
    'Рівненщина': 'Рівненська обл.',
    'Волинь': 'Волинська обл.',
    'Львівщина': 'Львівська обл.',
    'Тернопільщина': 'Тернопільська обл.',
    'Івано-Франківщина': 'Івано-Франківська обл.',
    'Закарпаття': 'Закарпатська обл.',
    'Кіровоградщина': 'Кіровоградська обл.'
}

# Мапінг міст на області (обласні центри та великі міста)
CITY_TO_REGION = {
    # Обласні центри
    'Київ': 'Київська обл.',
    'Харків': 'Харківська обл.',
    'Одеса': 'Одеська обл.',
    'Дніпро': 'Дніпропетровська обл.',
    'Донецьк': 'Донецька обл.',
    'Запоріжжя': 'Запорізька обл.',
    'Львів': 'Львівська обл.',
    'Кривий Ріг': 'Дніпропетровська обл.',
    'Миколаїв': 'Миколаївська обл.',
    'Маріуполь': 'Донецька обл.',
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
    # Інші великі міста
    'Охтирка': 'Сумська обл.',
    'Конотоп': 'Сумська обл.',
    'Шостка': 'Сумська обл.',
    'Ромни': 'Сумська обл.',
    'Ніжин': 'Чернігівська обл.',
    'Прилуки': 'Чернігівська обл.',
    'Кременчук': 'Полтавська обл.',
    'Павлоград': 'Дніпропетровська обл.',
    'Нікополь': 'Дніпропетровська обл.',
    'Марганець': 'Дніпропетровська обл.',
    'Кам\'янське': 'Дніпропетровська обл.',
    'Бердянськ': 'Запорізька обл.',
    'Мелітополь': 'Запорізька обл.',
    'Ізюм': 'Харківська обл.',
    'Куп\'янськ': 'Харківська обл.',
    'Лозова': 'Харківська обл.',
    'Біла Церква': 'Київська обл.',
    'Бровари': 'Київська обл.',
    'Бориспіль': 'Київська обл.',
    'Ірпінь': 'Київська обл.',
    'Фастів': 'Київська обл.',
    'Васильків': 'Київська обл.',
    'Умань': 'Черкаська обл.',
    'Сміла': 'Черкаська обл.',
    'Коростень': 'Житомирська обл.',
    'Бердичів': 'Житомирська обл.',
}


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
        
        # Пропускаємо рядки з "Підписатися", "ППОшник" тощо
        skip_keywords = ['Підписатися', 'ППОшник', 'Підпис', 'Telegram', 'Channel']
        if any(keyword in line for keyword in skip_keywords):
            continue
        
        # Пропускаємо рядки що містять тільки стрілки та символи
        if re.match(r'^[➡️⬅️↗️↘️↖️↙️⬆️⬇️\s]+$', line):
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


def parse_and_split_message(text):
    """
    Розбиває повідомлення на окремі повідомлення по населених пунктах
    """
    if not text:
        return []
    
    # Спочатку очищаємо текст
    text = clean_text(text)
    
    messages = []
    lines = text.strip().split('\n')
    current_region = None
    
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
        
        # Формат 1: "💥 Марганець (Дніпропетровська обл.)" або "🛸 Чернігів (Чернігівська обл.)"
        # Готові повідомлення з містом та областю (може бути текст після області)
        ready_match = re.match(r'^[💥🛸🛵⚠️❗️🔴👁️\s]*(.+?)\s*\((.+?обл\.?)\)', line)
        if ready_match:
            city = ready_match.group(1).strip()
            # Видаляємо emoji з назви міста
            city = re.sub(r'^[💥🛸🛵⚠️❗️🔴👁️\*\s]+', '', city).strip()
            city = re.sub(r'[\*]+', '', city).strip()
            region = ready_match.group(2).strip()
            if not region.endswith('.'):
                region = region + '.'
            
            # Шукаємо опис загрози в наступному рядку
            threat = threat_descriptions.get(i, "Загроза застосування БПЛА.")
            # Обрізаємо зайве
            threat = threat.split('.')[0] + '.' if '.' in threat else threat
            
            message = f"{city} ({region}) {threat}"
            messages.append(message)
            continue
        
        # Формат 2: "⚠️2х БпЛА на Шостку (Сумщина)" - місто і скорочена область в дужках
        short_region_match = re.match(r'^[💥🛸🛵⚠️❗️🔴👁️\s]*(\d*х?\s*)?(БпЛА|БПЛА|шахед[іиів]*)\s+(?:на\s+)?(.+?)\s*\((.+?)\)', line, re.IGNORECASE)
        if short_region_match:
            quantity = short_region_match.group(1) or ''
            city = short_region_match.group(3).strip()
            short_region = short_region_match.group(4).strip()
            
            # Конвертуємо скорочену назву області в повну
            region = REGION_MAP.get(short_region, short_region + ' обл.')
            
            message = f"{quantity}БПЛА {city} ({region}) Загроза застосування БПЛА."
            messages.append(message)
            continue
        
        # Формат 3: "⚠️8х БпЛА повз Кривий ріг на Кіровоградщину" - місто і область в тексті
        direction_match = re.match(r'^[💥🛸🛵⚠️❗️🔴👁️\s]*(\d*х?\s*)?(БпЛА|БПЛА|шахед[іиів]*)\s+(?:повз|на|курсом на)\s+(.+?)\s+(?:на|в|до)\s+(.+?)$', line, re.IGNORECASE)
        if direction_match:
            quantity = direction_match.group(1) or ''
            city = direction_match.group(3).strip()
            short_region = direction_match.group(4).strip()
            
            # Конвертуємо скорочену назву області в повну
            region = REGION_MAP.get(short_region, None)
            if not region and city in CITY_TO_REGION:
                region = CITY_TO_REGION[city]
            
            if region:
                message = f"{quantity}БПЛА {city} ({region}) Загроза застосування БПЛА."
                messages.append(message)
            continue
        
        # Перевіряємо чи це регіон
        is_region = False
        for region_key in REGION_MAP.keys():
            if region_key in line and ':' in line:
                current_region = REGION_MAP[region_key]
                is_region = True
                break
        
        if is_region:
            continue
        
        # Парсимо рядки з БпЛА/шахедами
        if any(keyword in line.lower() for keyword in ['бпла', 'шахед', 'шахід']):
            # Витягуємо кількість та текст
            # Формати: "2 шахеди на Чернігів", "2х БпЛА курсом на Київ", "БпЛА на Харків", "4 шахеди через Казанку в бік Кіровоградщини"
            
            # Спроба 1: "число + шахед/шахедів/шахеди + через + місто + в бік + область"
            match = re.match(r'(\d+)\s*(шахед[іиів]*|БпЛА|БПЛА)\s+через\s+(.+?)\s+в\s+бік\s+(.+)$', line, re.IGNORECASE)
            if match:
                quantity = match.group(1) + 'х ' if match.group(1) else ''
                city = match.group(3).strip()
                short_region = match.group(4).strip()
                region = REGION_MAP.get(short_region, current_region)
                if region:
                    message = f"{quantity}БПЛА {city} ({region}) Загроза застосування БПЛА."
                    messages.append(message)
                continue
            
            # Спроба 2: "число + шахед + кружляє біля/в районі + місто" (1 шахед кружляє біля Південноукраїнська)
            match = re.match(r'(\d+)\s*(шахед[іиів]*|БпЛА|БПЛА)\s+кружляє\s+(?:біля|в районі)\s+(.+)$', line, re.IGNORECASE)
            if match:
                quantity = match.group(1) + 'х ' if match.group(1) else ''
                city = match.group(3).strip()
                region = current_region
                if not region and city in CITY_TO_REGION:
                    region = CITY_TO_REGION[city]
                if region:
                    message = f"{quantity}БПЛА {city} ({region}) Загроза застосування БПЛА."
                    messages.append(message)
                continue
            
            # Спроба 3: "число + шахед + з + область + на + місто" (1 шахед з Сумщини на Талалаївку)
            match = re.match(r'(\d+)\s*(шахед[іиів]*|БпЛА|БПЛА)\s+з\s+\S+\s+на\s+(.+)$', line, re.IGNORECASE)
            if match:
                quantity = match.group(1) + 'х ' if match.group(1) else ''
                city = match.group(3).strip()
                region = current_region
                if not region and city in CITY_TO_REGION:
                    region = CITY_TO_REGION[city]
                if region:
                    message = f"{quantity}БПЛА {city} ({region}) Загроза застосування БПЛА."
                    messages.append(message)
                continue
            
            # Спроба 4: "число + шахед/шахедів/шахеди + на + місто" (1 шахед на Березнегувате)
            match = re.match(r'(\d+)\s*(шахед[іиів]*|БпЛА|БПЛА)\s+(?:курсом\s+)?на\s+(.+)$', line, re.IGNORECASE)
            if match:
                quantity = match.group(1) + 'х ' if match.group(1) else ''
                city = match.group(3).strip()
                # Видаляємо "с." на початку (с.Рівне -> Рівне)
                city = re.sub(r'^с\.', '', city).strip()
                region = current_region
                if not region and city in CITY_TO_REGION:
                    region = CITY_TO_REGION[city]
                if region:
                    message = f"{quantity}БПЛА {city} ({region}) Загроза застосування БПЛА."
                    messages.append(message)
                continue
            
            # Спроба 4: "числох БпЛА на місто"
            match = re.match(r'(\d+)х?\s*(БпЛА|БПЛА)\s*(?:курсом\s+)?(?:на\s+)?(.+)$', line, re.IGNORECASE)
            if match:
                quantity = match.group(1) + 'х ' if match.group(1) else ''
                city = match.group(3).strip()
                city = re.sub(r'\s*курсом.*$', '', city)
                city = re.sub(r'\s*з\s+.*$', '', city)
                city = city.strip()
                region = current_region
                if not region and city in CITY_TO_REGION:
                    region = CITY_TO_REGION[city]
                if city and region:
                    message = f"{quantity}БПЛА {city} ({region}) Загроза застосування БПЛА."
                    messages.append(message)
                continue
            
            # Спроба 5: "БпЛА на місто" (без числа)
            match = re.match(r'(БпЛА|БПЛА)\s*(?:курсом\s+)?(?:на\s+)?(.+)$', line, re.IGNORECASE)
            if match:
                quantity = ''
                city = match.group(2).strip()
                city = re.sub(r'\s*курсом.*$', '', city)
                city = re.sub(r'\s*з\s+.*$', '', city)
                city = city.strip()
                region = current_region
                if not region and city in CITY_TO_REGION:
                    region = CITY_TO_REGION[city]
                if city and region:
                    message = f"{quantity}БПЛА {city} ({region}) Загроза застосування БПЛА."
                    messages.append(message)
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
                    split_messages = parse_and_split_message(message.text)
                    
                    # Пропускаємо якщо немає валідних повідомлень
                    if not split_messages or (len(split_messages) == 1 and not split_messages[0]):
                        logger.info(f"⏭️ Пропущено повідомлення без конкретних локацій")
                        last_message_ids[channel] = message.id
                        continue
                    
                    # Пересилаємо кожне окреме повідомлення
                    try:
                        for split_msg in split_messages:
                            if not split_msg or not split_msg.strip():
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
                            # Невелика затримка між повідомленнями
                            await asyncio.sleep(0.5)
                        
                        # Оновлюємо ID
                        last_message_ids[channel] = message.id
                        forwarded_count += 1
                        logger.info(f"✅ Переслано з @{channel} в @{TARGET_CHANNEL}")
                        
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
    
    logger.info(f"\n📊 Моніторю {len(valid_sources)} каналів")
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
