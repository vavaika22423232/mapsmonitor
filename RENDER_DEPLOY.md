# RENDER DEPLOYMENT GUIDE

## 🚀 Деплой на Render.com

### Крок 1: Підготовка

1. Створіть Git репозиторій:
```bash
cd /Users/vladimirmalik/Desktop/telegram-forwarder
git init
git add .
git commit -m "Initial commit"
```

2. Завантажте на GitHub:
```bash
git remote add origin https://github.com/YOUR_USERNAME/telegram-forwarder.git
git push -u origin main
```

### Крок 2: Створення Background Worker на Render

1. Зайдіть на https://render.com
2. Натисніть **New** → **Background Worker**
3. Підключіть GitHub репозиторій
4. Заповніть налаштування:

**Name**: `telegram-forwarder`
**Environment**: `Python 3`
**Build Command**: `pip install -r requirements.txt`
**Start Command**: `python main.py`

### Крок 3: Environment Variables

Додайте наступні змінні в Render Dashboard:

```
TELEGRAM_API_ID=<your_id>
TELEGRAM_API_HASH=<your_hash>
TELEGRAM_SESSION=<your_string_session>
SOURCE_CHANNELS=UkraineAlarmSignal,kpszsu,war_monitor,napramok,raketa_trevoga,ukrainsiypposhnik
TARGET_CHANNEL=mapstransler
POLL_INTERVAL=30
DEDUP_INTERVAL=300
GROQ_API_KEY=<optional>
LOG_LEVEL=INFO
```

### Крок 4: Deploy

Натисніть **Create Background Worker**

Render автоматично:
- Завантажить код
- Встановить залежності
- Запустить бота

### 📊 Моніторинг

**Перегляд логів**: Render Dashboard → Logs

Ви побачите:
```
[INFO] Starting polling loop (interval: 30s)
[INFO] Connected as: <user>
[INFO] Target: @mapstransler
[INFO] Initial ID for @channel: <id>
```

### 🔄 Оновлення

Просто push в GitHub:
```bash
git add .
git commit -m "Update"
git push
```

Render автоматично передеплоїть!

### ⚠️ Troubleshooting

**Помилка авторизації?**
- Перевірте `TELEGRAM_SESSION` в Environment Variables
- Переконайтеся, що всі змінні правильно вставлені

**Бот не пересилає?**
- Перевірте, що акаунт є адміністратором @mapstransler
- Перевірте логи на Render

**З'єднання втрачено?**
- Render автоматично перезапустить бота
- Polling продовжить роботу з попереднього ID

### 💰 Вартість

- Render Free tier: **750 годин/місяць безкоштовно**
- Background Worker працює 24/7
- ~720 годин = 1 місяць роботи

### 🎯 Результат

Бот працює на Render 24/7 і автоматично пересилає повідомлення в @mapstransler!
