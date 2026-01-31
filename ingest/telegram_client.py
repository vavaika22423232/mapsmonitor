"""
Telegram client wrapper for message ingestion.
Handles connection, polling, and message retrieval.
"""
import asyncio
import logging
from typing import List, Optional, Dict, Any, AsyncIterator
from dataclasses import dataclass
from datetime import datetime

from telethon import TelegramClient
from telethon.sessions import StringSession

logger = logging.getLogger(__name__)


@dataclass
class IncomingMessage:
    """Wrapper for incoming Telegram message."""
    id: int
    text: str
    channel: str
    timestamp: datetime
    has_media: bool
    raw_message: Any  # Original Telethon message


class TelegramIngestClient:
    """
    Telegram client for message polling.
    
    Features:
    - StringSession support (for cloud deployment)
    - Connection management with auto-reconnect
    - Message ID tracking for deduplication
    - Batch polling from multiple channels
    """
    
    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session_string: str,
        source_channels: List[str],
        target_channel: str,
        poll_interval: int = 30
    ):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_string = session_string
        self.source_channels = [c.strip() for c in source_channels if c.strip()]
        self.target_channel = target_channel
        self.poll_interval = poll_interval
        
        self._client: Optional[TelegramClient] = None
        self._last_message_ids: Dict[str, int] = {}
        self._connected = False
    
    async def connect(self) -> bool:
        """Connect to Telegram and verify authorization."""
        try:
            self._client = TelegramClient(
                StringSession(self.session_string),
                self.api_id,
                self.api_hash
            )
            
            await self._client.connect()
            
            if not await self._client.is_user_authorized():
                logger.error("Session not authorized")
                return False
            
            me = await self._client.get_me()
            logger.info(f"Connected as: {me.first_name} (id: {me.id})")
            
            self._connected = True
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Telegram."""
        if self._client:
            await self._client.disconnect()
            self._connected = False
    
    async def ensure_connected(self) -> bool:
        """Ensure client is connected, reconnect if needed."""
        if not self._client:
            return await self.connect()
        
        if not self._client.is_connected():
            logger.info("Reconnecting...")
            try:
                await self._client.connect()
                if await self._client.is_user_authorized():
                    logger.info("Reconnected successfully")
                    return True
                else:
                    logger.error("Session expired")
                    return False
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")
                return False
        
        return True
    
    async def validate_channels(self) -> tuple:
        """
        Validate all configured channels.
        
        Returns:
            (valid_sources, target_entity) or raises exception
        """
        if not await self.ensure_connected():
            raise RuntimeError("Not connected")
        
        # Validate target
        try:
            target = await self._client.get_entity(self.target_channel)
            logger.info(f"Target channel: {target.title} (@{self.target_channel})")
        except Exception as e:
            raise RuntimeError(f"Target channel not found: {e}")
        
        # Validate sources
        valid_sources = []
        for channel in self.source_channels:
            try:
                entity = await self._client.get_entity(channel)
                valid_sources.append(channel)
                logger.info(f"Source channel: {entity.title} (@{channel})")
            except Exception as e:
                logger.warning(f"Source not found: @{channel} - {e}")
        
        if not valid_sources:
            raise RuntimeError("No valid source channels")
        
        return valid_sources, target
    
    async def poll_new_messages(self) -> AsyncIterator[IncomingMessage]:
        """
        Poll all source channels for new messages.
        
        Yields:
            IncomingMessage for each new message
        """
        if not await self.ensure_connected():
            return
        
        for channel in self.source_channels:
            try:
                entity = await self._client.get_entity(channel)
                
                async for message in self._client.iter_messages(entity, limit=1):
                    # First run - save ID and skip
                    if channel not in self._last_message_ids:
                        self._last_message_ids[channel] = message.id
                        logger.info(f"Initial ID for @{channel}: {message.id}")
                        continue
                    
                    # Check for new message
                    if message.id > self._last_message_ids[channel]:
                        logger.info(f"New message in @{channel}: ID {message.id}")
                        
                        yield IncomingMessage(
                            id=message.id,
                            text=message.text or "",
                            channel=channel,
                            timestamp=message.date,
                            has_media=bool(message.media),
                            raw_message=message
                        )
                        
                        self._last_message_ids[channel] = message.id
                        
            except Exception as e:
                logger.error(f"Error polling @{channel}: {e}")
    
    async def send_message(self, text: str, media=None) -> bool:
        """
        Send message to target channel.
        
        Args:
            text: Message text
            media: Optional media attachment
            
        Returns:
            True if sent successfully
        """
        if not await self.ensure_connected():
            return False
        
        try:
            if media:
                await self._client.send_message(
                    self.target_channel,
                    text,
                    file=media
                )
            else:
                await self._client.send_message(
                    self.target_channel,
                    text
                )
            return True
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False
    
    @property
    def is_connected(self) -> bool:
        return self._connected and self._client and self._client.is_connected()
    
    @property
    def client(self) -> Optional[TelegramClient]:
        return self._client
