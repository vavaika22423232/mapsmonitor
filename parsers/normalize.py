"""
Text normalization - clean and standardize input.
All normalization happens BEFORE parsing.
Uses morphological rules for Ukrainian language, no dictionaries.
"""
import re
from functools import lru_cache
from typing import Optional
from core.constants import REGION_ALIASES, SKIP_WORDS


# Precompiled patterns for normalization
_MARKDOWN = re.compile(r'\*\*|__|~~')
_URLS = re.compile(r'https?://[^\s]+')
_USERNAMES = re.compile(r'@\w+')
_EMOJI_ONLY = re.compile(r'^[➡️⬅️↗️↘️↖️↙️⬆️⬇️🇺🇦\s|]+$')
_SKIP_LINE = re.compile(
    r'Підписатися|ППОшник|Моніторинг 24/7|Радар України|Напрямок ракет|Карта повітряних тривог|Не фіксується|'
    r'Загроза для .*р-?в|передмісті\s+чисто|\bчисто\b'
)
_MULTI_SPACE = re.compile(r'\s+')
_EMOJI_PREFIX = re.compile(r'^[💥🛸🛵⚠️❗️🔴🚀✈️👁️📡\*\s]+')
_REGION_SUFFIX = re.compile(r'\s*\([^)]*(?:щина|ччина|область|обл\.?)[^)]*\)\s*$', re.IGNORECASE)


def normalize_text(text: str) -> str:
    """
    Clean raw message text for parsing.
    """
    if not text:
        return ""
    
    text = _MARKDOWN.sub('', text)
    
    lines = []
    for line in text.split('\n'):
        line = line.strip()
        
        if not line or line in ['ㅤ', '─' * len(line)]:
            continue
        
        if _SKIP_LINE.search(line):
            continue
        
        if _EMOJI_ONLY.match(line):
            continue
        
        line = _URLS.sub('', line)
        line = _USERNAMES.sub('', line)
        line = _MULTI_SPACE.sub(' ', line).strip()
        
        if line:
            lines.append(line)
    
    return '\n'.join(lines)


@lru_cache(maxsize=4096)
def normalize_city(city: str, use_ai: bool = False) -> str:
    """
    Normalize city name to nominative case using morphological rules.
    
    Ukrainian declension rules:
    - Genitive singular: -а/-я, -и/-і, -у/-ю -> nominative
    - Accusative: -у/-ю, -ку, -ну -> nominative  
    - Genitive plural: -ів/-їв, special forms -> nominative plural
    """
    if not city:
        return ""
    
    city = city.strip()
    
    # Remove emoji and special chars
    city = _EMOJI_PREFIX.sub('', city).strip()
    city = re.sub(r'[^\w\s\'\-]', '', city, flags=re.UNICODE).strip()
    
    # Remove prefixes
    city = re.sub(r'^(Район|бпла|БпЛА|БПЛА|БПЛA)\s*', '', city, flags=re.IGNORECASE).strip()
    city = re.sub(r'^на\s+', '', city, flags=re.IGNORECASE).strip()
    city = re.sub(r'^Ст\.\s*', '', city, flags=re.IGNORECASE).strip()
    
    # Remove region in parentheses
    city = _REGION_SUFFIX.sub('', city).strip()
    
    # Remove suffixes
    city = re.sub(r'\s+р-н$', '', city, flags=re.IGNORECASE)
    city = re.sub(r'\s+р$', '', city)
    
    # Remove trailing punctuation
    city = city.rstrip('.!?,;:')
    
    if not city:
        return ""
    
    # Handle multi-word cities
    words = city.split()
    if len(words) >= 2:
        return _normalize_multiword(words)
    
    # Single word
    return _normalize_single_word(city)


def _normalize_multiword(words: list) -> str:
    """Normalize multi-word city name."""
    if len(words) == 2:
        first, second = words[0], words[1]
        
        # "Кривого Рогу" -> "Кривий Ріг"
        # "Нову Каховку" -> "Нова Каховка"
        first_norm = _normalize_adjective(first)
        second_norm = _normalize_single_word(second)
        
        return f"{first_norm} {second_norm}"
    
    elif len(words) == 3:
        # "Біла Церква" type or with middle word
        return ' '.join(_normalize_single_word(w) for w in words)
    
    return ' '.join(words)


def _normalize_adjective(word: str) -> str:
    """
    Normalize adjective to nominative case.
    
    Rules:
    - Accusative feminine: -у -> -а (Нову -> Нова, Стару -> Стара)
    - Genitive masculine: -ого -> -ий (Кривого -> Кривий)
    - Genitive feminine: -ої -> -а (Козачої -> Козача)
    """
    if not word or len(word) < 3:
        return word
    
    lower = word.lower()
    
    # -ого -> -ий (Кривого -> Кривий, Білого -> Білий)
    if lower.endswith('ого'):
        stem = word[:-3]
        return stem + 'ий'
    
    # -ої -> -а (Козачої -> Козача, but careful with nouns)
    if lower.endswith('ої'):
        stem = word[:-2]
        return stem + 'а'
    
    # -у -> -а (Нову -> Нова, Стару -> Стара, Велику -> Велика, Малу -> Мала)
    if lower.endswith('у') and len(word) > 3:
        # Check it's likely an adjective (has typical adjective patterns)
        if lower.endswith(('ову', 'ару', 'ику', 'алу')):
            return word[:-1] + 'а'
    
    # Capitalize
    if word and word[0].islower():
        return word[0].upper() + word[1:]
    
    return word


def _normalize_single_word(word: str) -> str:
    """
    Normalize single word city name to nominative.
    
    KEY PRINCIPLE: Only transform words that are clearly in oblique case.
    Words already in nominative should pass through unchanged.
    
    Safe transformations (clear oblique markers):
    - -ку, -ну, -лю, -ію, -цю (accusative feminine)
    - -ого (genitive adjective/neuter)
    - -ів/-їв (genitive plural)
    - -ова/-єва (genitive masculine with vowel change)
    
    Unsafe (could be nominative):
    - -а, -и, -і, -у (could be nominative or oblique)
    """
    if not word or len(word) < 3:
        return _capitalize(word)
    
    lower = word.lower()
    
    # ============ SAFE: ACCUSATIVE -> NOMINATIVE ============
    # These endings are NEVER nominative for Ukrainian cities
    
    # -ку -> -ка (Васильківку -> Васильківка)
    if lower.endswith('ку'):
        return _capitalize(word[:-1] + 'а')
    
    # -ки -> -ка (Софіївки -> Софіївка) - genitive singular
    # BUT NOT for plural cities: Прилуки, Маяки, Черкаси
    plural_ki = {'прилуки', 'маяки', 'лубки', 'черки', 'суки'}
    if lower.endswith('ки') and len(word) > 4 and lower not in plural_ki:
        # Also skip -уки, -аки patterns (likely plural)
        if not lower.endswith(('уки', 'аки', 'оки')):
            return _capitalize(word[:-1] + 'а')
    
    # -ну -> -на (Просяну -> Просяна)
    if lower.endswith('ну') and len(word) > 3:
        return _capitalize(word[:-1] + 'а')
    
    # -лю -> -ля (Хотімлю -> Хотімля)
    if lower.endswith('лю'):
        return _capitalize(word[:-1] + 'я')
    
    # -ію -> -ія (Балаклію -> Балаклія)
    if lower.endswith('ію'):
        return _capitalize(word[:-1] + 'я')
    
    # -цю -> -ця
    if lower.endswith('цю'):
        return _capitalize(word[:-1] + 'я')
    
    # ============ SAFE: GENITIVE -> NOMINATIVE ============
    
    # -ого -> -е (Синельникового -> Синельникове)
    if lower.endswith('ого') and len(word) > 5:
        return _capitalize(word[:-3] + 'е')
    
    # -ів -> -и (Маяків -> Маяки, Циркунів -> Циркуни)
    # BUT NOT for cities ending in -ів as nominative (Харків, Київ, Львів, Чернігів, Очаків, Миколаїв)
    # These have -ів as part of the stem, not genitive plural ending
    nominative_iv = {
        'харків', 'київ', 'львів', 'чернігів', 'очаків', 'миколаїв',
        'дніпрів', 'черкасів', 'покровів', 'васильків', 'борислів',
        'калинів', 'любомирів', 'первомайськів', 'южноукраїнськів',
        'богодухів', 'куп\'янськів', 'вознесенськів', 'первомайськів'
    }
    if lower.endswith('ів') and len(word) > 3 and lower not in nominative_iv:
        # Only transform if it looks like genitive plural (5+ chars, stem >= 3)
        if len(word) >= 5:
            return _capitalize(word[:-2] + 'и')
    
    # -їв -> -ї (rare, mostly for foreign words)
    # NOT for Київ, Миколаїв - they are nominative
    nominative_jiv = {'київ', 'миколаїв'}
    if lower.endswith('їв') and len(word) > 4 and lower not in nominative_jiv:
        return _capitalize(word[:-2] + 'ї')
    
    # -ова -> -ів (Харкова -> Харків)
    if lower.endswith('ова') and len(word) > 4:
        stem = word[:-3]
        return _capitalize(stem + 'ів')
    
    # -єва -> -їв (Києва -> Київ)
    if lower.endswith('єва') and len(word) > 4:
        stem = word[:-3]
        return _capitalize(stem + 'їв')
    
    # ============ SPECIAL CASES (dictionary-like but minimal) ============
    # Only for cases where morphology alone can't determine the form
    
    special_cases = {
        # Genitive plural with zero ending -> nominative plural
        'сум': 'Суми',
        'черкас': 'Черкаси',
        'лубен': 'Лубни',
        'ромен': 'Ромни',
        'прилук': 'Прилуки',
        # Genitive with consonant cluster
        'конотопа': 'Конотоп',
        'лебедина': 'Лебедин',
        'павлограда': 'Павлоград',
        # Genitive from -а stem (plural)
        'маяка': 'Маяки',
        # Vowel alternation cases
        'рогу': 'Ріг',
        'рогa': 'Ріг',
        'ріг': 'Ріг',
    }
    
    if lower in special_cases:
        return special_cases[lower]
    
    # ============ CONSERVATIVE: Don't change if unsure ============
    # Words ending in -а, -и, -і, -у could be nominative, leave as is
    # The geocoder will validate
    
    return _capitalize(word)


def _is_likely_plural(lower: str) -> bool:
    """
    Check if word is likely a plural noun (nominative).
    Plural cities usually end in: -и, -і, -а
    """
    # Known plural city patterns
    plural_patterns = (
        'аки', 'оки', 'уки', 'ики',  # Маяки, Прилуки
        'аси', 'еси', 'оси',  # Черкаси
        'уми', 'оми',  # Суми
        'убни', 'омни',  # Лубни, Ромни
        'уни', 'они', 'ани', 'ини',  # Циркуни
    )
    return lower.endswith(plural_patterns)


def _capitalize(word: str) -> str:
    """Capitalize first letter."""
    if word and word[0].islower():
        return word[0].upper() + word[1:]
    return word


def normalize_region(region: str) -> Optional[str]:
    """
    Normalize region name to standard format "Назва обл."
    """
    if not region:
        return None
    
    region = region.strip()
    
    # Check alias mapping
    if region in REGION_ALIASES:
        return REGION_ALIASES[region]
    
    # Fix double "обл"
    region = re.sub(r'\s+обл\.?\s+обл\.?', ' обл.', region, flags=re.IGNORECASE)
    
    # Replace "область" with "обл."
    region = region.replace(' область', ' обл.').replace(' Область', ' обл.')
    
    # Ensure ends with "обл."
    if not region.endswith('обл.') and not region.endswith('обл'):
        if any(x in region.lower() for x in ['ська', 'цька', 'зька']):
            region = region.rstrip('.') + ' обл.'
    
    # Add period if missing
    if region.endswith(' обл'):
        region = region + '.'
    
    # Capitalize
    if region:
        region = region[0].upper() + region[1:]
    
    return region


def extract_region_from_alias(text: str) -> Optional[str]:
    """Extract region from text containing regional alias."""
    for alias, region in REGION_ALIASES.items():
        if alias.lower() in text.lower():
            return region
    return None


def is_skip_word(word: str) -> bool:
    """Check if word should be skipped."""
    return word.lower() in SKIP_WORDS
