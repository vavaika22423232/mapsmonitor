# Telegram Channel Forwarder

Автоматичне пересилання повідомлень з українських каналів тривоги до вашого Telegram‑каналу.

## 📋 Функції

- ✅ Модульна архітектура (інгест → парсинг → дедуп → відправка)
- ✅ Правила парсингу з пріоритетами та precompiled regex
- ✅ Rule-based парсинг з геокодінгом (CITIES + кеш + Visicom/OpenCage/Nominatim)
- ✅ Підтримка медіа
- ✅ Polling режим (перевірка кожні 30 секунд)
- ✅ Готовий до деплою на Render.com

## 🧱 Архітектура

- **Ingest**: підключення до Telegram та опитування каналів
- **Parsing**: нормалізація → правила → виділення сутностей
- **Core**: єдина модель `Event` та дедуп‑кеш
- **Geo**: геокодування міст через utils.geo (словник + кеш + API)

## ✅ Вимоги

- Python 3.10+
- Telegram API credentials

## 🚀 Швидкий старт (локально)

```bash
pip install -r requirements.txt
export TELEGRAM_API_ID=<your_id>
export TELEGRAM_API_HASH=<your_hash>
export TELEGRAM_SESSION=<your_string_session>
export SOURCE_CHANNELS=UkraineAlarmSignal,war_monitor,napramok
export TARGET_CHANNEL=mapstransler
python main.py
```

## 🚀 Деплой на Render

### 1. Створіть Telegram App
1. Перейдіть на https://my.telegram.org
2. Створіть додаток і отримайте `API_ID` та `API_HASH`

### 2. Отримайте Session String
Запустіть локально:
```bash
pip install telethon
python3 -c "from telethon.sync import TelegramClient; from telethon.sessions import StringSession; client = TelegramClient(StringSession(), input('API_ID: '), input('API_HASH: ')); client.start(); print('Session String:', client.session.save())"
```

### 3. Розгорніть на Render
1. Форкніть цей репозиторій
2. Створіть новий Web Service на [Render](https://render.com)
3. Підключіть ваш GitHub репозиторій
4. Додайте Environment Variables:
   - `TELEGRAM_API_ID` - ваш API ID
   - `TELEGRAM_API_HASH` - ваш API Hash
   - `TELEGRAM_SESSION` - ваш session string
   - `TARGET_CHANNEL` - канал для пересилання (наприклад, `mapstransler`)
   - `SOURCE_CHANNELS` - список каналів через кому
   - `POLL_INTERVAL` - інтервал перевірки в секундах (за замовчуванням 30)
   - `DEDUP_INTERVAL` - дедуплікація в секундах (за замовчуванням 300)

5. Deploy!

## 📡 Вихідні канали (приклад)

Бот моніторить наступні канали:
- @UkraineAlarmSignal - єТривога
- @kpszsu - Повітряні Сили ЗС України
- @war_monitor - Monitor
- @napramok - Напрямок ракет
- @raketa_trevoga - Чому тривога
- @ukrainsiypposhnik - Український ППОшник

## 🎯 Цільовий канал

Повідомлення пересилаються в: **@mapstransler**

## ⚙️ Налаштування (Environment Variables)

Всі налаштування через environment variables:

```
TELEGRAM_API_ID=<your_id>
TELEGRAM_API_HASH=<your_hash>
TELEGRAM_SESSION=<your_string_session>
SOURCE_CHANNELS=UkraineAlarmSignal,kpszsu,war_monitor,napramok,raketa_trevoga,ukrainsiypposhnik
TARGET_CHANNEL=mapstransler
POLL_INTERVAL=30
DEDUP_INTERVAL=300
LOG_LEVEL=INFO
```

## 🧪 Локальний запуск

```bash
python main.py
```

## ✅ Якість коду

```bash
pip install -r requirements-dev.txt
ruff check .
ruff format --check .
pytest -q
```

## ✅ Pre-commit

```bash
pip install -r requirements-dev.txt
pre-commit install
```

## 📝 Формат пересланих повідомлень

```
БПЛА Місто (Область обл.)
```

## 🛠️ Технічні деталі

- **Режим роботи**: Polling (опитування кожні 30 секунд)
- **Чому не events?**: Telegram User API не отримує real‑time події з публічних каналів
- **Сесія**: Зберігається в `test_session.session`

## 📊 Логи

Бот виводить детальні логи:
```
[INFO] Starting polling loop (interval: 30s)
[INFO] Connected as: <user>
[INFO] New message in @channel: ID <id>
[INFO] Sent: БПЛА Місто (Область обл.)
```

## ⚠️ Важливо

- Акаунт, що створив сесію, має бути адміністратором каналу‑цілі
- Бот бачить тільки **нові** повідомлення після запуску
- Файл `test_session.session` не треба комітити в Git!

## 🔒 Безпека

Не зберігайте сесію або ключі в репозиторії. Переконайтеся, що у `.gitignore` є:
```
*.session
*.session-journal
__pycache__/
*.pyc
.env
venv/
```

## 📞 Підтримка

Бот працює 24/7 і автоматично відновлюється після помилок.
