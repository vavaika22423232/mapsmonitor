"""
BPLA (drone) parsing rules.
Centralized BPLA extraction using shared entity extractor.
"""
from typing import List
from core.event import Event
from core.constants import ThreatType
from parsers.entity_extraction import extract_entities


def parse_bpla(text: str, channel: str = None) -> List[Event]:
    """
    Parse BPLA-related messages.
    
    Args:
        text: Raw message text
        channel: Source channel
        
    Returns:
        List of BPLA events
    """
    if not text:
        return []
    
    entities = extract_entities(text, channel)
    
    events = []
    for entity in entities:
        events.append(Event(
            type=ThreatType.BPLA,
            city=entity.city,
            region=entity.region,
            count=entity.count,
            source=channel or "",
            confidence=entity.confidence,
            raw_text=text
        ))
    
    return events
