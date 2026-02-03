"""Test Shahedy format parsing."""
from parsers.entity_extraction import extract_entities, _clean_city_name, get_region_for_city
from parsers.patterns import PATTERNS
from parsers.normalize import normalize_city, is_skip_word

msgs = [
    '🛵4х Шахеди на Вінницю!',
    '🛵12х Шахедів на Вінницю!!',
    '🛵9х Шахедів повз Умань на Вінниччину!',
]

for msg in msgs:
    print(f'\n=== {repr(msg)} ===')
    # Test pattern directly
    emoji_match = PATTERNS.location['emoji_count_threat_na_city'].search(msg)
    if emoji_match:
        print(f'  Pattern matched: count={emoji_match.group(1)}, city_raw={emoji_match.group(2)}')
        city_raw = emoji_match.group(2).strip()
        city = _clean_city_name(city_raw)
        print(f'  After clean: {repr(city)}')
        if city:
            normalized = normalize_city(city)
            print(f'  Normalized: {repr(normalized)}')
            region = get_region_for_city(normalized)
            print(f'  Region: {region}')
    else:
        print('  Pattern NOT matched')
    
    ents = extract_entities(msg)
    print(f'  Result: {[(e.city, e.region, e.count) for e in ents]}')
