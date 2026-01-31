"""
Message dispatcher - orchestrates the parsing pipeline.
Routes messages through normalization -> extraction -> classification -> dedup -> output.
"""
import asyncio
import logging
from typing import List, Optional

from .telegram_client import TelegramIngestClient, IncomingMessage
from core.event import Event, ThreatType
from core.cache import DeduplicationCache
from parsers.routing import route_message
from parsers.normalize import normalize_text
from parsers.patterns import PATTERNS
from ai.fallback import ai_fallback_parse, ai_enrich_events

logger = logging.getLogger(__name__)


class MessageDispatcher:
    """
    Central dispatcher for message processing pipeline.
    
    Pipeline:
    1. Receive raw message
    2. Normalize text
    3. Extract entities + classify threat
    4. Deduplicate
    5. Format and send
    """
    
    def __init__(
        self,
        telegram_client: TelegramIngestClient,
        dedup_ttl: int = 300,
        use_ai_fallback: bool = True
    ):
        self.telegram = telegram_client
        self.cache = DeduplicationCache(ttl_seconds=dedup_ttl)
        self.use_ai_fallback = use_ai_fallback
        
        self._processed_count = 0
        self._sent_count = 0
    
    async def process_message(self, message: IncomingMessage) -> int:
        """
        Process a single incoming message.
        
        Args:
            message: Incoming message from Telegram
            
        Returns:
            Number of alerts sent
        """
        if not message.text:
            return 0
        
        logger.debug(f"Processing message from @{message.channel}")
        
        # 1. Skip alert-only messages to avoid AI fallback noise
        normalized = normalize_text(message.text)
        if PATTERNS.skip['alerts'].search(normalized) or PATTERNS.skip['shelter'].search(normalized):
            logger.debug("Alert/shelter message skipped")
            return 0

        # 2. Parse message into events
        events = route_message(message.text, message.channel)

        # 3. AI enrich (max AI) on parsed events
        if events and self.use_ai_fallback:
            events = ai_enrich_events(events, message.text)
        
        # 4. AI fallback if no events found
        if not events and self.use_ai_fallback:
            events = ai_fallback_parse(message.text, message.channel)
        
        # 5. Filter invalid events
        events = [e for e in events if e.is_valid]
        
        if not events:
            logger.debug("No valid events found")
            return 0
        
        # 6. Deduplicate and send
        sent = 0
        for event in events:
            # Check deduplication
            if self.cache.check_and_add(event.dedup_key):
                age = self.cache.get_age(event.dedup_key)
                logger.info(f"Duplicate skipped: {event.dedup_key} (age: {age}s)")
                continue
            
            # Format and send
            formatted = event.format_message()
            if not formatted:
                continue
            
            # Send with media only for first message
            media = message.raw_message.media if sent == 0 and message.has_media else None
            
            if await self.telegram.send_message(formatted, media):
                sent += 1
                logger.info(f"Sent: {formatted}")
                await asyncio.sleep(0.5)  # Rate limiting
        
        self._processed_count += 1
        self._sent_count += sent
        
        return sent
    
    async def run_polling_loop(self):
        """
        Main polling loop - check for new messages and process them.
        """
        logger.info(f"Starting polling loop (interval: {self.telegram.poll_interval}s)")
        
        while True:
            try:
                async for message in self.telegram.poll_new_messages():
                    try:
                        sent = await self.process_message(message)
                        if sent:
                            logger.info(f"Processed @{message.channel}: {sent} alerts sent")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                
                await asyncio.sleep(self.telegram.poll_interval)
                
            except asyncio.CancelledError:
                logger.info("Polling loop cancelled")
                break
            except Exception as e:
                logger.error(f"Polling loop error: {e}")
                await asyncio.sleep(self.telegram.poll_interval)
    
    @property
    def stats(self) -> dict:
        """Get dispatcher statistics."""
        return {
            'processed': self._processed_count,
            'sent': self._sent_count,
            'cache_size': self.cache.size,
        }


async def create_and_run_dispatcher(
    api_id: int,
    api_hash: str,
    session: str,
    sources: List[str],
    target: str,
    poll_interval: int = 30,
    dedup_ttl: int = 300
) -> None:
    """
    Create dispatcher and run main loop.
    
    Convenience function for simple usage.
    """
    # Create Telegram client
    client = TelegramIngestClient(
        api_id=api_id,
        api_hash=api_hash,
        session_string=session,
        source_channels=sources,
        target_channel=target,
        poll_interval=poll_interval
    )
    
    # Connect
    if not await client.connect():
        raise RuntimeError("Failed to connect to Telegram")
    
    # Validate channels
    valid_sources, target_entity = await client.validate_channels()
    
    logger.info(f"Monitoring {len(valid_sources)} channels")
    logger.info(f"Target: @{target}")
    logger.info(f"Poll interval: {poll_interval}s")
    
    # Create dispatcher
    dispatcher = MessageDispatcher(
        telegram_client=client,
        dedup_ttl=dedup_ttl,
        use_ai_fallback=True
    )
    
    # Run
    try:
        await dispatcher.run_polling_loop()
    finally:
        await client.disconnect()
