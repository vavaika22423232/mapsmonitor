"""
Rocket and ballistic parsing rules.
Handles rockets, ballistic threats, and high-speed targets.
"""
from typing import List
from core.event import Event
from core.constants import ThreatType
from parsers.patterns import PATTERNS
from parsers.normalize import normalize_city, normalize_region
from parsers.entity_extraction import get_region_for_city


def parse_rockets(text: str, channel: str = None) -> List[Event]:
    """Parse rocket and ballistic-related messages."""
    if not text:
        return []
    
    events = _parse_ballistic_global(text, channel)
    if events:
        return events
    
    events = _parse_grupa_kr(text, channel)
    if events:
        return events
    
    events = _parse_rocket_city(text, channel)
    if events:
        return events
    
    events = _parse_ballistic_city(text, channel)
    if events:
        return events
    
    return _parse_highspeed_city(text, channel)


def _parse_ballistic_global(text: str, channel: str) -> List[Event]:
    if not PATTERNS.rocket['zagroza_ballistyka'].search(text):
        return []
    if '(' in text:
        return []
    
    return [Event(
        type=ThreatType.BALLISTIC,
        source=channel or "",
        confidence=0.9,
        raw_text=text
    )]


def _parse_rocket_city(text: str, channel: str) -> List[Event]:
    match = PATTERNS.rocket['raketa_kursom'].search(text)
    if not match:
        return []
    
    city = normalize_city(match.group(1))
    region = get_region_for_city(city)
    if not city or not region:
        return []
    
    return [Event(
        type=ThreatType.ROCKET,
        city=city,
        region=region,
        source=channel or "",
        confidence=0.9,
        raw_text=text
    )]


def _parse_ballistic_city(text: str, channel: str) -> List[Event]:
    match = PATTERNS.rocket['ballistika_na'].search(text)
    if not match:
        return []
    
    city = normalize_city(match.group(1))
    region = get_region_for_city(city)
    if not city or not region:
        return []
    
    return [Event(
        type=ThreatType.BALLISTIC,
        city=city,
        region=region,
        source=channel or "",
        confidence=0.9,
        raw_text=text
    )]


def _parse_highspeed_city(text: str, channel: str) -> List[Event]:
    match = PATTERNS.rocket['vysokoshvydkisni'].search(text)
    if not match:
        return []
    
    city = normalize_city(match.group(1))
    region = normalize_region(match.group(2))
    if not city or not region:
        return []
    
    return [Event(
        type=ThreatType.ROCKET,
        city=city,
        region=region,
        source=channel or "",
        confidence=0.95,
        raw_text=text
    )]


def _parse_grupa_kr(text: str, channel: str) -> List[Event]:
    """Parse 'Група КР курсом на City' format."""
    match = PATTERNS.location['grupa_kr_kursom'].search(text)
    if not match:
        return []
    
    count = int(match.group(1)) if match.group(1) else None
    city = normalize_city(match.group(2).strip())
    region = get_region_for_city(city)
    if not city or not region:
        return []
    
    return [Event(
        type=ThreatType.ROCKET,
        city=city,
        region=region,
        count=count,
        source=channel or "",
        confidence=0.9,
        raw_text=text
    )]
