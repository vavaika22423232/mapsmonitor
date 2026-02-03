"""
AI fallback logic - use AI when rule-based parsing fails.
Never mutates raw text.
"""
import logging
from typing import List, Optional

from .groq_client import get_client
from core.event import Event
from core.constants import ThreatType, REGION_ALIASES, SKIP_WORDS
from parsers.normalize import normalize_city

logger = logging.getLogger(__name__)


def ai_fallback_parse(text: str, source: str = "") -> List[Event]:
    """
    Parse message using AI when regex-based parsing fails.
    
    This is a TRUE FALLBACK - only called when:
    1. Rule-based parsing returned no results
    2. Message is long enough to contain meaningful data
    3. AI client is available
    
    Args:
        text: Original message text (never mutated)
        source: Source channel name
        
    Returns:
        List of parsed events (may be empty)
    """
    client = get_client()
    
    if not client.is_available:
        return []
    
    if not text or len(text) < 20:
        return []
    
    text_lower = text.lower()
    # Skip AI on non-threat informational text
    if not any(k in text_lower for k in [
        'бпла', 'шахед', 'дрон', 'ракета', 'каб', 'пуск', 'вибух', 'обстріл'
    ]):
        return []

    logger.info(f"AI fallback for: {text[:100]}...")
    
    try:
        results = client.parse_message(text)
        
        if not results:
            return []
        
        region_alias_map = {k.lower(): v.lower() for k, v in REGION_ALIASES.items()}
        events = []
        for item in results:
            city = item.get('city', '')
            region = item.get('region', '')
            threat_type_str = item.get('type', 'БПЛА')
            
            if not city or not region:
                continue
            
            # Skip if city is a known non-location
            if city.lower() in SKIP_WORDS:
                continue

            # Require city or region presence in original text (anti-hallucination)
            city_lower = city.lower()
            city_normalized = normalize_city(city).lower()
            city_in_text = city_lower in text_lower or city_normalized in text_lower

            region_lower = region.lower()
            region_in_text = (
                region_lower in text_lower
                or region_lower.replace(' обл.', '') in text_lower
                or any(alias in text_lower and mapped == region_lower for alias, mapped in region_alias_map.items())
            )

            if not (city_in_text or region_in_text):
                logger.info(f"AI skipped hallucinated city: {city}")
                continue

            # Determine threat type
            threat_type = ThreatType.from_string(threat_type_str)
            
            events.append(Event(
                type=threat_type,
                city=city,
                region=region,
                source=source,
                confidence=0.7,  # Lower confidence for AI results
                raw_text=text
            ))
        
        if events:
            logger.info(f"AI fallback found {len(events)} events")
        
        return events
        
    except Exception as e:
        logger.warning(f"AI fallback error: {e}")
        return []


def ai_normalize_city(city: str) -> str:
    """
    Use AI to normalize city name if rule-based normalization fails.
    
    Args:
        city: City name in any case
        
    Returns:
        Normalized city name (nominative case)
    """
    client = get_client()
    
    if not client.is_available:
        return city
    
    return client.normalize_city(city)


def ai_validate_city_region(city: str, region: str) -> tuple:
    """
    Use AI to validate city-region pair.
    
    Args:
        city: City name
        region: Parsed region
        
    Returns:
        (city, validated_region) - may correct region if wrong
    """
    client = get_client()
    
    if not client.is_available:
        return city, region
    
    return client.validate_city_region(city, region)


def ai_get_region(city: str, hint: str = None) -> Optional[str]:
    """
    Use AI to determine region for a city.
    
    Args:
        city: City name
        hint: Optional region hint
        
    Returns:
        Region or None
    """
    client = get_client()
    
    if not client.is_available:
        return None
    
    return client.get_region(city, hint)


def ai_enrich_events(events: List[Event], hint_text: str = "") -> List[Event]:
    """
    Enrich parsed events with AI validation and region filling.

    - If region is missing, try to infer it from AI.
    - If region exists, validate/correct it with AI.
    """
    client = get_client()
    if not client.is_available or not events:
        return events

    enriched = []
    for event in events:
        if event.city and not event.region:
            event.region = client.get_region(event.city, hint_text) or event.region
        if event.city and event.region:
            _, validated = client.validate_city_region(event.city, event.region)
            event.region = validated
        enriched.append(event)

    return enriched
