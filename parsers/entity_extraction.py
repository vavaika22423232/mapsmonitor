"""
Entity extraction - extract cities, regions, counts from text.
Uses centralized patterns and priority-based matching.
"""
import re
from typing import List, Optional
from dataclasses import dataclass
import logging

from .patterns import PATTERNS
from .normalize import normalize_city, normalize_region, is_skip_word
from core.constants import CITIES, REGION_ALIASES, CHANNEL_REGIONS

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEntity:
    """Extracted location entity."""
    city: str
    region: str
    count: Optional[int] = None
    confidence: float = 1.0
    pattern_name: str = ""


def extract_entities(text: str, channel: str = None) -> List[ExtractedEntity]:
    """
    Extract all location entities from text.
    
    Uses priority-based pattern matching:
    1. Most specific patterns first (city + region in parens)
    2. Region header patterns (sets context)
    3. City-only patterns (use context or geocoding)
    """
    if not text:
        return []
    
    entities = []
    current_region = CHANNEL_REGIONS.get(channel) if channel else None
    
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        
        if PATTERNS.skip['alerts'].search(line) or PATTERNS.skip['shelter'].search(line):
            continue
        
        header_match = _extract_region_header(line)
        if header_match:
            current_region = header_match
            continue
        
        entity = _extract_city_region_parens(line)
        if entity:
            entities.append(entity)
            continue
        
        region_cities = _extract_region_colon_cities(line, current_region)
        if region_cities:
            entities.extend(region_cities)
            continue
        
        entity = _extract_with_context(line, current_region)
        if entity:
            entities.append(entity)
            continue
        
        entity = _extract_arrow_city(line, current_region)
        if entity:
            entities.append(entity)
    
    return [e for e in entities if _is_valid_entity(e)]


def _extract_region_header(line: str) -> Optional[str]:
    clean = re.sub(r'^[✈️🛵🛸⚠️❗️🔴📡\s]+', '', line).strip()
    match = re.match(r'^(\S+(?:\s+область)?):?\s*$', clean, re.IGNORECASE)
    if match:
        region_name = match.group(1).strip()
        if region_name in REGION_ALIASES:
            return REGION_ALIASES[region_name]
        if 'област' in region_name.lower():
            return normalize_region(region_name)
    return None


def _extract_city_region_parens(line: str) -> Optional[ExtractedEntity]:
    match = PATTERNS.location['city_region_parens'].search(line)
    if not match:
        return None
    
    city_raw = match.group(1).strip()
    region_raw = match.group(2).strip()
    
    city = _clean_city_name(city_raw)
    if not city or is_skip_word(city):
        return None
    
    if city in REGION_ALIASES:
        return None
    
    city = normalize_city(city)
    region = normalize_region(region_raw)
    if not region:
        return None
    
    return ExtractedEntity(
        city=city,
        region=region,
        confidence=0.95,
        pattern_name='city_region_parens'
    )


def _extract_region_colon_cities(line: str, default_region: str = None) -> List[ExtractedEntity]:
    match = PATTERNS.location['region_colon_cities'].search(line)
    if not match:
        return []
    
    region_name = match.group(1).strip()
    cities_part = match.group(2).strip()
    
    region = REGION_ALIASES.get(region_name)
    if not region and 'област' in region_name.lower():
        region = normalize_region(region_name)
    if not region:
        region = default_region
    if not region:
        return []
    
    entities = []
    for entry in re.split(r',\s*', cities_part):
        city = _extract_city_from_entry(entry)
        if city and not is_skip_word(city):
            city = normalize_city(city)
            entities.append(ExtractedEntity(
                city=city,
                region=region,
                confidence=0.9,
                pattern_name='region_colon_cities'
            ))
    
    return entities


def _extract_with_context(line: str, current_region: str) -> Optional[ExtractedEntity]:
    if not current_region:
        return None
    
    match = PATTERNS.location['count_threat_na_city'].search(line)
    if match:
        count = int(match.group(1))
        city = _clean_city_name(match.group(2))
        if city and not is_skip_word(city):
            return ExtractedEntity(
                city=normalize_city(city),
                region=current_region,
                count=count,
                confidence=0.85,
                pattern_name='count_threat_na_city'
            )
    
    match = PATTERNS.location['bpla_kursom_na'].search(line)
    if match:
        city = _clean_city_name(match.group(1))
        if city and not is_skip_word(city):
            return ExtractedEntity(
                city=normalize_city(city),
                region=current_region,
                confidence=0.85,
                pattern_name='bpla_kursom_na'
            )
    
    match = PATTERNS.location['n_v_rayoni'].search(line)
    if match:
        count = int(match.group(1))
        city = _clean_city_name(match.group(2))
        if city and not is_skip_word(city):
            return ExtractedEntity(
                city=normalize_city(city),
                region=current_region,
                count=count,
                confidence=0.8,
                pattern_name='n_v_rayoni'
            )
    
    return None


def _extract_arrow_city(line: str, current_region: str) -> Optional[ExtractedEntity]:
    if not current_region:
        return None
    
    match = PATTERNS.location['arrow_city'].match(line)
    if not match:
        return None
    
    content = match.group(1).strip()
    if content in REGION_ALIASES:
        return None
    
    if '/' in content:
        parts = content.split('/')
        city = parts[-1].strip()
        if city.lower() in ['р-н', 'район', 'околиці'] or city in REGION_ALIASES:
            city = parts[0].strip()
    else:
        city = content
    
    city = _clean_city_name(city)
    if not city or is_skip_word(city):
        return None
    
    return ExtractedEntity(
        city=normalize_city(city),
        region=current_region,
        confidence=0.8,
        pattern_name='arrow_city'
    )


def _extract_city_from_entry(entry: str) -> Optional[str]:
    entry = entry.strip()
    
    match = re.match(r'^\d+\s+(?:на|в районі|біля|повз)\s+(.+?)$', entry, re.IGNORECASE)
    if match:
        return match.group(1).strip().rstrip('.,;')
    
    match = re.match(r'^\d+\s+([А-ЯІЇЄҐа-яіїєґ\'\-\s]+)$', entry, re.IGNORECASE)
    if match:
        return match.group(1).strip().rstrip('.,;')
    
    match = re.match(r'^\d+\s*х?\s*шахед[іиів]*\s+на\s+(.+?)$', entry, re.IGNORECASE)
    if match:
        return match.group(1).strip().rstrip('.,;')
    
    match = re.match(r'^(?:БпЛА|БПЛА)\s+курсом\s+на\s+(.+?)$', entry, re.IGNORECASE)
    if match:
        return match.group(1).strip().rstrip('.,;')
    
    return None


def _clean_city_name(city: str) -> str:
    if not city:
        return ""
    
    city = city.strip()
    city = re.sub(r'^[💥🛸🛵⚠️❗️🔴🚀✈️👁️\*\s]+', '', city)
    city = re.sub(r'[💥🛸🛵⚠️❗️🔴🚀✈️👁️]+', '', city)
    city = re.sub(r'^\d+\s*х?\s*', '', city)
    city = re.sub(r'^(?:БПЛА|БпЛА|шахед[іиів]*)\s*', '', city, flags=re.IGNORECASE)
    city = re.sub(r'\s+з\s+\S+щин[иіу]?\s*$', '', city, flags=re.IGNORECASE)
    city = re.sub(r'\s+з\s+\S+ччин[иіу]?\s*$', '', city, flags=re.IGNORECASE)
    city = re.sub(r'\s+[ву]\s+бік\s+.+$', '', city, flags=re.IGNORECASE)
    city = re.sub(r'\s+курсом\s+на\s+.+$', '', city, flags=re.IGNORECASE)
    if ' та ' in city:
        city = city.split(' та ')[0].strip()
    city = city.strip().rstrip('.,;!?')
    return city


def _is_valid_entity(entity: ExtractedEntity) -> bool:
    if not entity.city or not entity.region:
        return False
    if len(entity.city) < 2:
        return False
    if PATTERNS.direction_words.match(entity.city):
        return False
    if is_skip_word(entity.city):
        return False
    if entity.city in REGION_ALIASES:
        return False
    return True


def get_region_for_city(city: str, hint_region: str = None) -> Optional[str]:
    if city in CITIES:
        return CITIES[city]
    city_cap = city[0].upper() + city[1:] if city else city
    if city_cap in CITIES:
        return CITIES[city_cap]
    return hint_region
