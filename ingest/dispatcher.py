"""
Message dispatcher - orchestrates the parsing pipeline.
Routes messages through normalization -> extraction -> classification -> dedup -> output.
"""
import asyncio
import logging
import re
from typing import List, Optional

from .telegram_client import TelegramIngestClient, IncomingMessage
from core.event import Event, ThreatType
from core.cache import DeduplicationCache
from parsers.routing import route_message
from utils.geo import geocode_city
from parsers.classification import validate_city_region
from core.constants import REGION_ALIASES, CITY_TO_REGION, SKIP_WORDS
from parsers.normalize import normalize_text
from parsers.patterns import PATTERNS
from ai.fallback import ai_fallback_parse, ai_enrich_events

logger = logging.getLogger(__name__)

INFO_ATTACK_KEYWORDS = (
    'запланував', 'передислокац', 'плануємо', 'планують',
    'пріоритет для ураження', 'ймовірні цілі', 'майбутн',
    'попереджений - значить озброєний'
)
NEUTRALIZED_KEYWORDS = (
    'зникла', 'зникли', 'зник на', 'ціль зникла', 'цілі зникли',
    'збито', 'знищено', 'втрачено ціль', 'втрачена ціль'
)
AIRCRAFT_KEYWORDS = (
    'у повітрі', 'борти ту-', 'борт ту-', 'літак ту-',
    'бомбардувальник', 'стратегічн', 'з аеродрома', 'з аеродрому'
)


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
        self.raw_cache = DeduplicationCache(ttl_seconds=120)
        self.use_ai_fallback = use_ai_fallback
        self._normalize_cache = {}
        self._normalize_cache_order = []
        
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
        
        # 1. Normalize text with small cache
        cache_key = f"{message.channel}:{message.id}"
        normalized = self._normalize_cache.get(cache_key)
        if normalized is None:
            normalized = normalize_text(message.text)
            self._normalize_cache[cache_key] = normalized
            self._normalize_cache_order.append(cache_key)
            if len(self._normalize_cache_order) > 512:
                old_key = self._normalize_cache_order.pop(0)
                self._normalize_cache.pop(old_key, None)
        normalized_lower = normalized.lower()

        # 1.0. Skip informational/planned messages
        if any(k in normalized_lower for k in INFO_ATTACK_KEYWORDS):
            logger.debug("Informational planned attack message skipped")
            return 0

        # 1.0. Skip neutralized targets (good news)
        if any(k in normalized_lower for k in NEUTRALIZED_KEYWORDS):
            logger.debug("Neutralized target message skipped")
            return 0

        # 1.0. Skip aircraft status messages
        if any(k in normalized_lower for k in AIRCRAFT_KEYWORDS):
            logger.debug("Aircraft status message skipped")
            return 0

        # 1.1. Soft dedup by raw text (avoid repeated channel spam)
        raw_key = normalized_lower.strip()
        if raw_key and self.raw_cache.check_and_add(raw_key):
            logger.debug("Raw text duplicate skipped")
            return 0

        # 2. Skip alert-only messages to avoid AI fallback noise
        is_alert = PATTERNS.skip['alerts'].search(normalized) or PATTERNS.skip['shelter'].search(normalized)
        has_threat = (
            PATTERNS.threat_type.match_any(normalized)
            or PATTERNS.launch['keywords'].search(normalized)
        )
        if is_alert and not has_threat:
            logger.debug("Alert/shelter message skipped")
            return 0

        # Skip city-only messages without threat keywords
        if not has_threat and re.match(r'^\W*[А-ЯІЇЄҐа-яіїєґ\'\-]+\W*$', normalized):
            logger.debug("City-only message skipped (no threat)")
            return 0

        # 2. Parse message into events
        events = route_message(message.text, message.channel)

        # 2.5. Enrich events with empty region via geocode (cache + API)
        for event in events:
            if event.city and not event.region:
                region = await geocode_city(event.city)
                if region:
                    event.region = region

        # 3. Local validation on parsed events (skip if header region exists)
        header_region = _detect_region_header(normalized)
        if events and not header_region:
            for event in events:
                if event.city and event.region:
                    corrected = validate_city_region(event.city, event.region)[1]
                    if corrected:
                        event.region = corrected

        # 4. AI enrich (max AI) on parsed events
        if events and self.use_ai_fallback:
            events = ai_enrich_events(events, message.text)
        
        # 5. AI fallback if no events found
        if not events and self.use_ai_fallback:
            events = ai_fallback_parse(message.text, message.channel)
        
        # 6. Filter invalid events
        events = [e for e in events if e.is_valid]
        
        if not events:
            logger.debug("No valid events found")
            return 0
        
        # 7. Deduplicate and send
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


def _detect_region_header(text: str) -> Optional[str]:
    """Detect region header in message (e.g., "Харківщина:" or "Харківська область:")."""
    if not text:
        return None
    for line in text.split('\n'):
        clean = line.strip().lstrip('✈️🛵🛸⚠️❗️🔴📡 ').strip()
        if not clean:
            continue
        if clean.endswith(':'):
            clean = clean[:-1].strip()
        if clean in REGION_ALIASES:
            return REGION_ALIASES[clean]
        if 'област' in clean.lower():
            return clean.replace(' область', ' обл.').replace(' Область', ' обл.')
    return None

    


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
