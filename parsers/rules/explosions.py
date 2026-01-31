"""
Explosion parsing rules.
"""
import re
from typing import List
from core.event import Event
from core.constants import ThreatType
from parsers.patterns import PATTERNS
from parsers.normalize import normalize_city, normalize_region
from parsers.entity_extraction import get_region_for_city


def parse_explosions(text: str, channel: str = None) -> List[Event]:
    """
    Parse explosion-related messages.
    
    Returns:
        List of explosion events
    """
    if not text:
        return []
    
    events: List[Event] = []
    
    # "City (Region) ... вибухи"
    match = re.search(
        r'^[⚠️❗️💥\s]*(.+?)\s*\((.+?обл\.?)\)[\s\n]*(?:ЗМІ\s+)?повідомляють\s+про\s+вибухи',
        text,
        re.IGNORECASE | re.MULTILINE
    )
    if match:
        city = normalize_city(match.group(1))
        region = normalize_region(match.group(2))
        if city and region:
            events.append(Event(
                type=ThreatType.EXPLOSION,
                city=city,
                region=region,
                source=channel or "",
                confidence=0.95,
                raw_text=text
            ))
        return events
    
    # "City - вибухи"
    match = PATTERNS.location['city_explosion'].search(text)
    if match:
        city = normalize_city(match.group(1))
        if city:
            region = get_region_for_city(city)
            if region:
                events.append(Event(
                    type=ThreatType.EXPLOSION,
                    city=city,
                    region=region,
                    source=channel or "",
                    confidence=0.85,
                    raw_text=text
                ))
        return events

    # "💥 City (Region) ... Загроза обстрілу"
    match = re.search(
        r'^[💥⚠️❗️\s]*(.+?)\s*\((.+?обл\.?)\)[\s\n]*'
        r'Загроза\s+обстрілу',
        text,
        re.IGNORECASE | re.MULTILINE
    )
    if match:
        city = normalize_city(match.group(1))
        region = normalize_region(match.group(2))
        if city and region:
            events.append(Event(
                type=ThreatType.EXPLOSION,
                city=city,
                region=region,
                source=channel or "",
                confidence=0.9,
                raw_text=text
            ))
        return events
    
    return events
