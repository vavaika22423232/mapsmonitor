#!/usr/bin/env python3
"""
Генератор STRING_SESSION для Telegram
Запусти цей скрипт локально для отримання нової сесії
"""

from telethon.sync import TelegramClient
from telethon.sessions import StringSession
import os

API_ID = input("Введіть API_ID: ")
API_HASH = input("Введіть API_HASH: ")

with TelegramClient(StringSession(), int(API_ID), API_HASH) as client:
    session_string = client.session.save()
    print("\n" + "="*50)
    print("Ваша STRING_SESSION:")
    print("="*50)
    print(session_string)
    print("="*50)
    print("\nСкопіюйте цей рядок і вставте в TELEGRAM_SESSION на Render")
