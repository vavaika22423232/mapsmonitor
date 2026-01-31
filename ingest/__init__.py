"""Ingest module - Telegram client and message dispatching."""
from .telegram_client import TelegramIngestClient
from .dispatcher import MessageDispatcher

__all__ = ['TelegramIngestClient', 'MessageDispatcher']
