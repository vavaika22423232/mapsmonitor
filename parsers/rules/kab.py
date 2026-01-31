"""
KAB (guided bomb) parsing rules.
"""
from typing import List
from core.event import Event
from core.constants import ThreatType
from parsers.patterns import PATTERNS
from parsers.normalize import normalize_city, normalize_region
from parsers.entity_extraction import get_region_for_city
import re


def parse_kab(text: str, channel: str = None) -> List[Event]:
    """Parse KAB-related messages."""
    if not text:
        return []
    
    events = _parse_zagroza(text, channel)
    if events:
        return events
    
    events = _parse_aviatsiya(text, channel)
    if events:
        return events
    
    return _parse_rayon(text, channel)


def _parse_zagroza(text: str, channel: str) -> List[Event]:
    match = PATTERNS.kab['zagroza_kab'].search(text)
    if not match:
        return []
    
    city = normalize_city(match.group(1))
    region = normalize_region(match.group(2))
    if not city or not region:
        return []
    
    return [Event(
        type=ThreatType.KAB,
        city=city,
        region=region,
        source=channel or "",
        confidence=0.95,
        raw_text=text
    )]


def _parse_aviatsiya(text: str, channel: str) -> List[Event]:
    match = PATTERNS.kab['aviatsiya_kab'].search(text)
    if not match:
        return []
    
    events: List[Event] = []
    cities_part = match.group(1).strip()
    for city in re.split(r'[/,]', cities_part):
        city = normalize_city(city.strip())
        if not city:
            continue
        region = get_region_for_city(city)
        if not region:
            continue
        events.append(Event(
            type=ThreatType.KAB,
            city=city,
            region=region,
            source=channel or "",
            confidence=0.9,
            raw_text=text
        ))
    
    return events


def _parse_rayon(text: str, channel: str) -> List[Event]:
    match = PATTERNS.kab['kab_rayon'].search(text)
    if not match:
        return []
    
    district = match.group(1).strip()
    region = normalize_region(match.group(2))
    if not district or not region:
        return []
    
    return [Event(
        type=ThreatType.KAB,
        city=district,
        region=region,
        source=channel or "",
        confidence=0.9,
        raw_text=text
    )]
