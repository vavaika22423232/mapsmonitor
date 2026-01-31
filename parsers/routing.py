"""
Routing logic - apply rule priority and return events.
"""
from typing import List
from core.event import Event
from core.constants import ThreatType
from parsers.normalize import normalize_text
from parsers.patterns import PATTERNS
from parsers.rules import parse_kab, parse_rockets, parse_explosions, parse_bpla


def route_message(text: str, channel: str = None) -> List[Event]:
    """
    Route message through prioritized rules.
    
    Priority:
    1. All-clear ballistic (filter)
    2. KAB
    3. Rockets / Ballistic
    4. Explosions
    5. BPLA
    """
    if not text:
        return []
    
    # Normalize for parsing
    normalized = normalize_text(text)
    if not normalized:
        return []
    
    # 1. Ballistic all-clear
    if PATTERNS.rocket['vidbiy_ballistyka'].search(normalized):
        return [Event(
            type=ThreatType.BALLISTIC,
            raw_text=text,
            source=channel or "",
            confidence=0.95
        )]
    
    # 2. KAB
    events = parse_kab(normalized, channel)
    if events:
        return events
    
    # 3. Rockets / Ballistic
    events = parse_rockets(normalized, channel)
    if events:
        return events
    
    # 4. Explosions
    events = parse_explosions(normalized, channel)
    if events:
        return events
    
    # 5. BPLA (default)
    return parse_bpla(normalized, channel)
