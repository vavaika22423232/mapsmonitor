"""
RECON (reconnaissance drone) parsing rules.
Same extraction as BPLA, but event type RECON.
"""
from typing import List
from core.event import Event
from core.constants import ThreatType
from parsers.entity_extraction import extract_entities
from parsers.patterns import PATTERNS


def parse_recon(text: str, channel: str = None) -> List[Event]:
    """
    Parse reconnaissance drone messages.
    Uses same entity extraction as BPLA but outputs RECON type.
    """
    if not text:
        return []

    # Must have recon keywords
    if not PATTERNS.threat_type['recon'].search(text):
        return []

    entities = extract_entities(text, channel)

    events = []
    for entity in entities:
        events.append(Event(
            type=ThreatType.RECON,
            city=entity.city,
            region=entity.region,
            count=entity.count,
            source=channel or "",
            confidence=entity.confidence,
            raw_text=text
        ))

    return events
