"""
Launch (BPLA) parsing rules for Russian launch locations.
"""
from typing import List
import re

from core.event import Event
from core.constants import ThreatType
from parsers.patterns import PATTERNS
from parsers.normalize import normalize_city


def parse_launches(text: str, channel: str = None) -> List[Event]:
    """Parse launch-related messages and return launch events."""
    if not text:
        return []

    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if not any(PATTERNS.launch['keywords'].search(line) for line in lines):
        return []

    locations = []
    in_context = False

    for line in lines:
        if PATTERNS.launch['keywords'].search(line):
            in_context = True
        match = PATTERNS.launch['source_location'].search(line)
        if match:
            loc = _clean_launch_location(match.group(1))
            if loc:
                locations.append(loc)
                continue
        if in_context:
            plus_match = PATTERNS.launch['plus_location'].match(line)
            if plus_match:
                loc = _clean_launch_location(plus_match.group(1))
                if loc:
                    locations.append(loc)

    events = []
    for loc in _dedup(locations):
        events.append(Event(
            type=ThreatType.LAUNCH,
            city=loc,
            region='РФ',
            source=channel or "",
            confidence=0.8,
            raw_text=text
        ))

    return events


def _clean_launch_location(raw: str) -> str:
    if not raw:
        return ""
    cleaned = raw.strip()
    cleaned = re.sub(r'[\s\.,;:!]+$', '', cleaned)
    cleaned = re.sub(r'\(.*?\)', '', cleaned).strip()
    cleaned = cleaned.replace('аеродром', '').replace('аеродрому', '').replace('аеродрома', '')
    cleaned = cleaned.replace('ае', '').replace('а/е', '').strip()
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    return normalize_city(cleaned)


def _dedup(items: List[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
