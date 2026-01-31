"""
Threat classification helpers.
"""
from core.constants import ThreatType, CITIES
from parsers.patterns import PATTERNS


def classify_threat(text: str) -> ThreatType:
    """
    Determine threat type from message text.
    
    Priority order:
    1. Ballistic
    2. Rocket
    3. KAB
    4. Explosion
    5. BPLA
    """
    if not text:
        return ThreatType.UNKNOWN
    
    text_lower = text.lower()
    
    if PATTERNS.rocket['zagroza_ballistyka'].search(text):
        return ThreatType.BALLISTIC
    if PATTERNS.rocket['ballistika_na'].search(text):
        return ThreatType.BALLISTIC
    if any(x in text_lower for x in ['ракет', 'калібр', 'крилат']):
        return ThreatType.ROCKET
    if PATTERNS.rocket['vysokoshvydkisni'].search(text):
        return ThreatType.ROCKET
    if any(x in text_lower for x in ['каб', 'кабів']):
        return ThreatType.KAB
    if 'загроза застосування кабів' in text_lower:
        return ThreatType.KAB
    if '💥' in text or 'вибух' in text_lower:
        return ThreatType.EXPLOSION
    if any(x in text_lower for x in ['бпла', 'шахед', 'герань', 'мопед', 'балалайк']):
        return ThreatType.BPLA
    
    return ThreatType.UNKNOWN


def validate_city_region(city: str, region: str) -> tuple:
    """Validate that city belongs to region and correct if needed."""
    if not city or not region:
        return city, region
    
    known_region = CITIES.get(city)
    if known_region and known_region != region:
        return city, known_region
    
    return city, region
