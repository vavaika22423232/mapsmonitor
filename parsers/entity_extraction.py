"""
Entity extraction - extract cities, regions, counts from text.
Uses centralized patterns and priority-based matching.
"""
import re
from typing import List, Optional
from dataclasses import dataclass
import logging

from .patterns import PATTERNS
from .normalize import normalize_city, normalize_region, extract_region_from_alias, is_skip_word
from core.constants import CITIES, REGION_ALIASES, CHANNEL_REGIONS
from utils.geo import get_region_for_city

REGION_ALIASES_LOWER = {k.lower() for k in REGION_ALIASES}
SUMMARY_COUNT_RE = re.compile(r'^\s*[А-ЯІЇЄҐа-яіїєґ\s]+—\s*\d+х\s*$')
SUMMARY_HEADER_RE = re.compile(r'^\s*По\s+БпЛА\b', re.IGNORECASE)
SPECIAL_ATTENTION_RE = re.compile(r'^Особлива\s+увага\s*:\s*(.*)$', re.IGNORECASE)
MAX_ATTENTION_ITEMS = 80

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
    
    special_attention = False
    attention_buffer: List[str] = []

    for line in text.strip().split('\n'):
        line = line.strip()
        if not line:
            if special_attention and attention_buffer:
                cities_text = ', '.join(attention_buffer)
                entities.extend(_build_entities_from_city_list(
                    cities_text,
                    None,
                    None,
                    0.7,
                    'special_attention'
                ))
                attention_buffer = []
            special_attention = False
            continue
        
        if PATTERNS.skip['alerts'].search(line) or PATTERNS.skip['shelter'].search(line):
            continue

        # Skip regional summary counts like "Сумщина — 1х"
        if SUMMARY_COUNT_RE.match(line):
            continue
        if SUMMARY_HEADER_RE.match(line):
            continue

        # Parse "Особлива увага" blocks with city list
        attention_match = SPECIAL_ATTENTION_RE.match(line)
        if attention_match:
            special_attention = True
            tail = attention_match.group(1).strip()
            if tail:
                attention_buffer.append(tail)
            continue
        if special_attention:
            attention_buffer.append(line)
            if len(attention_buffer) >= MAX_ATTENTION_ITEMS:
                cities_text = ', '.join(attention_buffer)
                entities.extend(_build_entities_from_city_list(
                    cities_text,
                    None,
                    None,
                    0.7,
                    'special_attention'
                ))
                attention_buffer = []
                special_attention = False
            continue
        
        inline_header = _extract_inline_region_header(line)
        if inline_header:
            current_region, line = inline_header

        header_match = _extract_region_header(line)
        if header_match:
            current_region = header_match
            continue

        entity = _extract_city_region_parens(line)
        if entity:
            entities.append(entity)
            continue

        entity = _extract_kursom_na_city_region(line)
        if entity:
            entities.append(entity)
            continue

        entity = _extract_city_region_alias_parens(line)
        if entity:
            entities.append(entity)
            continue
        
        region_cities = _extract_region_colon_cities(line, current_region)
        if region_cities:
            entities.extend(region_cities)
            continue
        
        # "✈️ City/р-н - обережно по БПЛА!" - extract city and geocode
        oberezhno_entities = _extract_oberezhno_bpla(line)
        if oberezhno_entities:
            entities.extend(oberezhno_entities)
            continue
        
        context_entities = _extract_with_context(line, current_region)
        if context_entities:
            entities.extend(context_entities)
            continue
        
        arrow_entities = _extract_arrow_city(line, current_region)
        if arrow_entities:
            entities.extend(arrow_entities)
    
    if special_attention and attention_buffer:
        cities_text = ', '.join(attention_buffer)
        entities.extend(_build_entities_from_city_list(
            cities_text,
            None,
            None,
            0.7,
            'special_attention'
        ))

    return [e for e in entities if _is_valid_entity(e)]


def _extract_region_header(line: str) -> Optional[str]:
    clean = re.sub(r'^[✈️🛵🛸⚠️❗️🔴📡\s]+', '', line).strip()
    match = re.match(r'^(\S+(?:\s+область)?):?\s*$', clean, re.IGNORECASE)
    if match:
        region_name = match.group(1).strip().rstrip(':')
        if region_name in REGION_ALIASES:
            return REGION_ALIASES[region_name]
        if 'област' in region_name.lower():
            return normalize_region(region_name)
    return None


def _extract_inline_region_header(line: str) -> Optional[tuple]:
    clean = re.sub(r'^[✈️🛵🛸⚠️❗️🔴📡\s]+', '', line).strip()
    match = re.match(r'^(\S+(?:\s+область)?):\s*(.+)$', clean, re.IGNORECASE)
    if not match:
        return None

    region_name = match.group(1).strip().rstrip(':')
    remainder = match.group(2).strip()
    region = REGION_ALIASES.get(region_name)
    if not region and 'област' in region_name.lower():
        region = normalize_region(region_name)
    if not region:
        return None
    return region, remainder


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


def _extract_kursom_na_city_region(line: str) -> Optional[ExtractedEntity]:
    """Extract from 'X курсом на City (Region обл.)' format."""
    match = PATTERNS.location['kursom_na_city_region'].search(line)
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
        confidence=0.9,
        pattern_name='kursom_na_city_region'
    )


def _extract_city_region_alias_parens(line: str) -> Optional[ExtractedEntity]:
    match = PATTERNS.location['city_region_alias_parens'].search(line)
    if not match:
        return None

    city_raw = match.group(1).strip()
    region_raw = match.group(2).strip()

    city = _clean_city_name(city_raw)
    if not city or is_skip_word(city):
        return None

    city = normalize_city(city)
    region = normalize_region(region_raw) or extract_region_from_alias(region_raw)
    if not region:
        return None

    return ExtractedEntity(
        city=city,
        region=region,
        confidence=0.9,
        pattern_name='city_region_alias_parens'
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


def _extract_oberezhno_bpla(line: str) -> List[ExtractedEntity]:
    """Extract city from '✈️ City/р-н - обережно по БПЛА!' pattern."""
    match = PATTERNS.location['oberezhno_bpla'].search(line)
    if not match:
        return []
    
    city_raw = match.group(1).strip()
    city = _clean_city_name(city_raw)
    if not city or is_skip_word(city):
        return []
    
    city = normalize_city(city)
    
    # Get region from geo (CITIES + cache)
    region = get_region_for_city(city)
    if not region:
        return []
    
    return [ExtractedEntity(
        city=city,
        region=region,
        confidence=0.85,
        pattern_name='oberezhno_bpla'
    )]


def _extract_with_context(line: str, current_region: str) -> List[ExtractedEntity]:
    region = current_region or extract_region_from_alias(line)
    if not region:
        return []

    entities: List[ExtractedEntity] = []
    
    match = PATTERNS.location['from_city_to_city'].search(line)
    if match:
        count = int(match.group(1)) if match.group(1) else None
        cities_text = match.group(3)
        if cities_text:
            entities.extend(_build_entities_from_city_list(
                cities_text,
                region,
                count,
                0.85,
                'from_city_to_city'
            ))
            return entities
    
    match = PATTERNS.location['count_threat_na_city'].search(line)
    if match:
        count = int(match.group(1))
        cities_text = match.group(2)
        if cities_text:
            entities.extend(_build_entities_from_city_list(
                cities_text,
                region,
                count,
                0.85,
                'count_threat_na_city'
            ))
            return entities

    match = PATTERNS.location['count_na_city'].search(line)
    if match:
        count = int(match.group(1))
        cities_text = match.group(2)
        if cities_text:
            entities.extend(_build_entities_from_city_list(
                cities_text,
                region,
                count,
                0.8,
                'count_na_city'
            ))
            return entities

    match = PATTERNS.location['count_city'].search(line)
    if match:
        count = int(match.group(1))
        cities_text = match.group(2)
        if cities_text:
            entities.extend(_build_entities_from_city_list(
                cities_text,
                region,
                count,
                0.75,
                'count_city'
            ))
            return entities

    match = PATTERNS.location['kursom_na_city'].search(line)
    if match:
        cities_text = match.group(1)
        if cities_text:
            entities.extend(_build_entities_from_city_list(
                cities_text,
                region,
                None,
                0.75,
                'kursom_na_city'
            ))
            return entities

    match = PATTERNS.location['moves_to_city'].search(line)
    if match:
        cities_text = match.group(1)
        if cities_text:
            entities.extend(_build_entities_from_city_list(
                cities_text,
                region,
                None,
                0.75,
                'moves_to_city'
            ))
            return entities
    
    match = PATTERNS.location['bpla_kursom_na'].search(line)
    if match:
        cities_text = match.group(1)
        if cities_text:
            entities.extend(_build_entities_from_city_list(
                cities_text,
                region,
                None,
                0.85,
                'bpla_kursom_na'
            ))
            return entities
    
    # "✈️ City/р-н - обережно по БПЛА!"
    match = PATTERNS.location['oberezhno_bpla'].search(line)
    if match:
        cities_text = match.group(1)
        if cities_text:
            entities.extend(_build_entities_from_city_list(
                cities_text,
                region,
                None,
                0.85,
                'oberezhno_bpla'
            ))
            return entities
    
    match = PATTERNS.location['n_v_rayoni'].search(line)
    if match:
        count = int(match.group(1))
        cities_text = match.group(2)
        if cities_text:
            entities.extend(_build_entities_from_city_list(
                cities_text,
                region,
                count,
                0.8,
                'n_v_rayoni'
            ))
            return entities

    match = PATTERNS.location['threat_bilya_city'].search(line)
    if match:
        cities_text = match.group(1)
        if cities_text:
            entities.extend(_build_entities_from_city_list(
                cities_text,
                region,
                None,
                0.8,
                'threat_bilya_city'
            ))
            return entities

    match = PATTERNS.location['v_bik_city'].search(line)
    if match:
        cities_text = match.group(1)
        if cities_text:
            entities.extend(_build_entities_from_city_list(
                cities_text,
                region,
                None,
                0.75,
                'v_bik_city'
            ))
            return entities

    match = PATTERNS.location['v_rayoni_city'].search(line)
    if match:
        cities_text = match.group(1)
        if cities_text:
            entities.extend(_build_entities_from_city_list(
                cities_text,
                region,
                None,
                0.75,
                'v_rayoni_city'
            ))
            return entities

    match = PATTERNS.location['threat_nad_city'].search(line)
    if match:
        cities_text = match.group(1)
        if cities_text:
            entities.extend(_build_entities_from_city_list(
                cities_text,
                region,
                None,
                0.8,
                'threat_nad_city'
            ))
            return entities

    match = PATTERNS.location['po_shahedu_na'].search(line)
    if match:
        cities_text = match.group(1)
        if cities_text:
            entities.extend(_build_entities_from_city_list(
                cities_text,
                region,
                1,
                0.75,
                'po_shahedu_na'
            ))
            return entities

    match = PATTERNS.location['city_to_you'].search(line)
    if match:
        cities_text = match.group(1)
        if cities_text:
            entities.extend(_build_entities_from_city_list(
                cities_text,
                region,
                None,
                0.75,
                'city_to_you'
            ))
            return entities

    return entities


def _extract_arrow_city(line: str, current_region: str) -> List[ExtractedEntity]:
    region = current_region or extract_region_from_alias(line)
    if not region:
        return []
    
    match = PATTERNS.location['arrow_city'].match(line)
    if not match:
        arrow_index = max(line.rfind('→'), line.rfind('➡️'))
        if arrow_index >= 0:
            content = line[arrow_index + 1:].strip()
        else:
            return []
    else:
        content = match.group(1).strip()
    
    if content in REGION_ALIASES:
        return []
    
    cities = _split_cities(content)
    entities: List[ExtractedEntity] = []
    for city in cities:
        city = _clean_city_name(city)
        if not city or is_skip_word(city):
            continue
        entities.append(ExtractedEntity(
            city=normalize_city(city),
            region=region,
            confidence=0.8,
            pattern_name='arrow_city'
        ))

    return entities


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

    match = re.match(r'^\d+\s+(?:біля|поблизу)\s+(.+?)$', entry, re.IGNORECASE)
    if match:
        return match.group(1).strip().rstrip('.,;')

    match = re.match(r'^(?:кружляє|крутиться)\s+біля\s+(.+?)$', entry, re.IGNORECASE)
    if match:
        return match.group(1).strip().rstrip('.,;')

    match = re.match(r'^(?:шахед|БпЛА|БПЛА)\s+над\s+(.+?)$', entry, re.IGNORECASE)
    if match:
        return match.group(1).strip().rstrip('.,;')
    
    return None


def _clean_city_name(city: str) -> str:
    if not city:
        return ""
    
    city = city.strip()
    city = re.sub(r'^[💥🛸🛵⚠️❗️🔴🚀✈️👁️•▪️\*\s]+', '', city)
    city = re.sub(r'\([^)]*\)?', '', city).strip()  # Remove incomplete parens too
    city = re.sub(r'[💥🛸🛵⚠️❗️🔴🚀✈️👁️]+', '', city)
    city = re.sub(r'^\d+\s*х?\s*', '', city)
    city = re.sub(r'^(?:БПЛА|БпЛА|БПЛA|шахед[іиів]*)\s*', '', city, flags=re.IGNORECASE)
    city = re.sub(r'^(?:останній|крутиться|кружляє|кружляють|маневрує|маневрують|крутяться)\s+', '', city, flags=re.IGNORECASE)
    city = re.sub(r'^(?:між|поміж)\s+', '', city, flags=re.IGNORECASE)
    # Clean movement phrases
    city = re.sub(r'^(?:продовжує\s+рух\s+на|у\s+напрямку|в\s+напрямку|на|рух\s+на)\s+', '', city, flags=re.IGNORECASE)
    city = re.sub(r'^(?:летят\s+в\s+сторону|летить\s+на|пока|поки)\s+', '', city, flags=re.IGNORECASE)
    # Remove "в/у Чорному морі" phrases
    city = re.sub(r'\s*[ву]\s+чорному\s+мор[іюя].*$', '', city, flags=re.IGNORECASE)
    # Remove trailing movement words
    city = re.sub(r'\s+крутяться\s*$', '', city, flags=re.IGNORECASE)
    city = re.sub(r'\s+з\s+\S+щин[иіу]?\s*$', '', city, flags=re.IGNORECASE)
    city = re.sub(r'\s+з\s+\S+ччин[иіу]?\s*$', '', city, flags=re.IGNORECASE)
    city = re.sub(r'\s+з\s+чорного\s+моря\s*$', '', city, flags=re.IGNORECASE)
    city = re.sub(r'\s+з\s+моря\s*$', '', city, flags=re.IGNORECASE)
    city = re.sub(r'\s+[ву]\s+бік\s+.+$', '', city, flags=re.IGNORECASE)
    city = re.sub(r'\s+курсом\s+на\s+.+$', '', city, flags=re.IGNORECASE)
    # Remove district suffix "р-н" attached to city name
    city = re.sub(r'р-н\s*$', '', city, flags=re.IGNORECASE)
    # Split glued words like "Очаківсела" -> "Очаків"
    city = re.sub(r'(ів|ка|ки|не|ин|ів)(?:села|міста|району|області)\s*$', r'\1', city, flags=re.IGNORECASE)
    # Split CamelCase glued words like "ГалициновеМиколаї" -> take first word "Галицинове"
    camel_match = re.match(r'^([А-ЯІЇЄҐ][а-яіїєґ\']+)([А-ЯІЇЄҐ][а-яіїєґ\']+)$', city)
    if camel_match:
        city = camel_match.group(1)  # Take first word only
    if ' та ' in city:
        city = city.split(' та ')[0].strip()
    city = city.strip().rstrip('.,;!?')

    city_lower = city.lower()
    # Skip garbage
    if len(city) < 3:
        return ""
    # Skip common non-city words and truncated prefixes
    # Note: removed 'зап' - conflicts with Запоріжжя
    if city_lower in ('на', 'над', 'під', 'до', 'від', 'через', 'біля', 'коло', 'рух', 'курс', 'курсом', 'шт', 'кам', 'сам', 'дні', 'хар', 'пол', 'оде', 'мик', 'берегом', 'берег', 'море', 'морем'):
        return ""
    # Skip common nouns that are not cities
    garbage_words = {'небо', 'столба', 'столб', 'застава', 'заставу', 'сторону', 'напрямок', 'напрямку', 
                     'північ', 'південь', 'схід', 'захід', 'центр', 'район', 'села', 'міста', 'області',
                     'ракета', 'ракети', 'ракету', 'дрон', 'дрона', 'дрони', 'бпла', 'шахед', 'каб',
                     'летит', 'летить', 'літає', 'коси', 'косу', 'косі', 'коса'}
    if city_lower in garbage_words:
        return ""
    if 'невизначеного' in city_lower and 'тип' in city_lower:
        return ""
    if 'бпла' in city_lower or 'шахед' in city_lower:
        return ""
    # Note: removed REGION_ALIASES check - city names like "Запоріжжя" are also cities
    if city_lower.endswith('щина') or city_lower.endswith('ччина') or city_lower.endswith('щини'):
        return ""
    if 'межі' in city_lower or 'межа' in city_lower:
        return ""
    if city_lower.startswith('з '):
        return ""
    # Skip districts (району, район)
    if 'район' in city_lower:
        return ""
    # Skip region names (область)
    if 'область' in city_lower:
        return ""
    # Skip phrases not cities
    if 'центр області' in city_lower or 'маневр' in city_lower:
        return ""
    # Skip geographic features (not settlements)
    if 'коси' in city_lower or 'коса' in city_lower or 'косу' in city_lower:
        return ""
    # Skip Russian phrases
    if 'сторону' in city_lower or 'летят' in city_lower or 'пока' in city_lower:
        return ""
    # Skip Russian city forms (should be Ukrainian)
    if city_lower.endswith('ска') or city_lower.endswith('ского'):
        return ""
    # Skip incomplete words like "Арий" (truncated "Старий")
    if city_lower in ('арий', 'арій', 'овий', 'ий', 'ій'):
        return ""
    if city_lower.startswith('арий ') or city_lower.startswith('арій '):
        return ""

    return city


def _split_cities(content: str) -> List[str]:
    parts = re.split(r'\s*(?:,|\s+та\s+|/)\s*', content)
    filtered = []
    for part in parts:
        if not part:
            continue
        low = part.lower()
        if low in ['р-н', 'р-ну', 'р-на', 'район', 'околиці']:
            continue
        if part in REGION_ALIASES or low in REGION_ALIASES_LOWER:
            continue
        filtered.append(part)
    return filtered


def _build_entities_from_city_list(
    cities_text: str,
    region: str,
    count: Optional[int],
    confidence: float,
    pattern: str
) -> List[ExtractedEntity]:
    entities: List[ExtractedEntity] = []
    for city in _split_cities(cities_text):
        if any(dash in city for dash in ['-', '–', '—']):
            parts = re.split(r'\s*[-–—]\s*', city, maxsplit=1)
            if len(parts) == 2:
                left, right = [c.strip() for c in parts]
                left_norm = normalize_city(left, use_ai=False) or left
                right_norm = normalize_city(right, use_ai=False) or right
                if left_norm in CITIES and right_norm in CITIES:
                    for part in (left_norm, right_norm):
                        entities.extend(_build_entities_from_city_list(
                            part,
                            region,
                            count,
                            confidence,
                            pattern
                        ))
                    continue
        direction_match = PATTERNS.location['v_bik_city'].search(city)
        if direction_match:
            city = direction_match.group(1)
        city = _clean_city_name(city)
        if not city or is_skip_word(city):
            continue
        normalized_city = normalize_city(city)
        resolved_region = region or get_region_for_city(normalized_city, region)
        entities.append(ExtractedEntity(
            city=normalized_city,
            region=resolved_region,
            count=count,
            confidence=confidence,
            pattern_name=pattern
        ))
    return entities


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


