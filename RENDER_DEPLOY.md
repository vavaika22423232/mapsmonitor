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
**Start Command**: `python channel_forwarder_polling.py`

### Крок 3: Environment Variables

Додайте наступні змінні в Render Dashboard:

```
TELEGRAM_API_ID=24031340
TELEGRAM_API_HASH=2daaa58652e315ce52adb1090313d36a
TELEGRAM_SESSION=1BJWap1sBuy6rg3J6zXFs4Xtq-nKAqnHnKjxRIh7T3rmY4zF1YRHhhDX9UzPzw29NLqAVArSEV-XFx2KWHBZEQxsOLHLArWEgLkH2L_Q9-5p8zR5qnQU-yd8XXh0gGP5IAptyEcpM-U0FVi3lNaOBdAN9KqLko8Q0HfuzEaeJSu_tRV7rAHCcP1qd-CbeB9NQ8eZM-eSMph2nahucd__C27fJreae5OUaDgi6-jwxuoeJJsfv-wGTJWyZ1mmdCQL_Zg3nfVw8P0MEiIQG2Ha4WWPBD3ZF9TEg3w0Uhis2obwHJ3CRNM9nPg7fZH1dN29lUeAznpnnHVzPip0TBrZp0sE1n6qeru4=
SOURCE_CHANNELS=UkraineAlarmSignal,kpszsu,war_monitor,napramok,raketa_trevoga,ukrainsiypposhnik
TARGET_CHANNEL=mapstransler
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
[INFO] 🚀 Запуск Channel Forwarder (Polling mode)...
[INFO] ✅ Авторизовано: / (263781966038)
[INFO] ✅ Цільовий канал: mapstransler_bot
[INFO] 📌 UkraineAlarmSignal: збережено початковий ID 365882
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
