#!/bin/bash

echo "🚀 Запуск Telegram Channel Forwarder..."
echo ""
echo "📋 Перевірка залежностей..."

# Перевірка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 не знайдено!"
    exit 1
fi

echo "✅ Python 3: $(python3 --version)"

# Встановлення залежностей
if [ ! -d "venv" ]; then
    echo "📦 Створення віртуального середовища..."
    python3 -m venv venv
fi

echo "📦 Активація віртуального середовища..."
source venv/bin/activate

echo "📦 Встановлення залежностей..."
pip install -r requirements.txt

echo ""
echo "🎯 Запуск бота..."
echo ""

python3 channel_forwarder_polling.py
