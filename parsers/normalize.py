"""
Text normalization - clean and standardize input.
All normalization happens BEFORE parsing.
"""
import re
from typing import Optional
from core.constants import REGION_ALIASES, CITY_CASE_TRANSFORMS, SKIP_WORDS, CITIES


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
    
    Removes:
    - Markdown formatting
    - URLs and usernames
    - Advertisement/channel info lines
    - Excessive whitespace
    
    Args:
        text: Raw message text
        
    Returns:
        Cleaned text ready for parsing
    """
    if not text:
        return ""
    
    # Remove markdown
    text = _MARKDOWN.sub('', text)
    
    # Process line by line
    lines = []
    for line in text.split('\n'):
        line = line.strip()
        
        # Skip empty or whitespace-only
        if not line or line in ['ㅤ', '─' * len(line)]:
            continue
        
        # Skip advertisement lines
        if _SKIP_LINE.search(line):
            continue
        
        # Skip emoji-only lines
        if _EMOJI_ONLY.match(line):
            continue
        
        # Remove URLs and usernames
        line = _URLS.sub('', line)
        line = _USERNAMES.sub('', line)
        
        # Normalize whitespace
        line = _MULTI_SPACE.sub(' ', line).strip()
        
        if line:
            lines.append(line)
    
    return '\n'.join(lines)


def normalize_city(city: str, use_ai: bool = True) -> str:
    """
    Normalize city name to nominative case.
    
    Handles:
    - Case transformations (accusative/genitive -> nominative)
    - Emoji removal
    - Prefix cleanup ("Район", "bpla", etc.)
    - Two-word city fixes ("Нову Миколаївку" -> "Нова Миколаївка")
    - AI normalization for unknown cases (if use_ai=True)
    
    Args:
        city: Raw city name
        use_ai: Use AI for normalization if rule-based fails
        
    Returns:
        Normalized city name in nominative case
    """
    if not city:
        return ""
    
    original_city = city
    city = city.strip()
    
    # Remove emoji and special chars
    city = _EMOJI_PREFIX.sub('', city).strip()
    city = re.sub(r'[^\w\s\'\-]', '', city, flags=re.UNICODE).strip()
    
    # Remove prefixes
    city = re.sub(r'^(Район|бпла|БпЛА|БПЛА)\s+', '', city, flags=re.IGNORECASE).strip()
    city = re.sub(r'^на\s+', '', city, flags=re.IGNORECASE).strip()
    city = re.sub(r'^Ст\.?\s*', '', city, flags=re.IGNORECASE).strip()
    
    # Remove region in parentheses from city name
    city = _REGION_SUFFIX.sub('', city).strip()
    
    # Remove suffixes
    city = re.sub(r'\s+р-н$', ' район', city, flags=re.IGNORECASE)
    city = re.sub(r'\s+р$', ' район', city)
    
    # Remove trailing punctuation
    city = city.rstrip('.!?,;:')
    
    # Check known transformations first
    city_lower = city.lower()
    if city_lower in CITY_CASE_TRANSFORMS:
        return CITY_CASE_TRANSFORMS[city_lower]
    
    # Handle two-word cities ("Нову Миколаївку" -> "Нова Миколаївка")
    words = city.split()
    if len(words) == 2:
        first, second = words[0], words[1]
        first_fixed = _fix_adjective_case(first)
        second_fixed = _fix_noun_case(second)
        if first_fixed != first or second_fixed != second:
            normalized = f"{first_fixed} {second_fixed}"
            # Check if result is in known cities
            if normalized in CITIES:
                return normalized
    
    # Single word transformations
    normalized = _fix_noun_case(city)
    
    # If result is in known cities, return it
    if normalized in CITIES:
        return normalized
    
    # If AI enabled and city changed but not in known list, try AI normalization
    if use_ai and normalized != original_city and normalized not in CITIES:
        try:
            from ai.fallback import ai_normalize_city
            ai_result = ai_normalize_city(city)
            if ai_result and ai_result != city:
                return ai_result
        except Exception:
            pass  # Fallback to rule-based result
    
    return normalized


def _fix_adjective_case(word: str) -> str:
    """Fix adjective case (Нову -> Нова, etc.)"""
    lower = word.lower()
    transforms = {
        'нову': 'Нова', 'стару': 'Стара',
        'велику': 'Велика', 'малу': 'Мала',
    }
    return transforms.get(lower, word)


def _fix_noun_case(word: str) -> str:
    """Fix noun case to nominative."""
    if not word or len(word) < 3:
        return word
    
    original = word
    lower = word.lower()
    
    # Known transforms
    if lower in CITY_CASE_TRANSFORMS:
        return CITY_CASE_TRANSFORMS[lower]
    
    # Rules for genitive case -> nominative
    # -ова/-ева -> -ів (Харкова -> Харків, but Нова stays Нова)
    if lower.endswith('ова') and len(word) > 4:
        # Check if it's an adjective (Нова, Стара) - these should stay as is
        if lower not in ['нова', 'стара', 'велика', 'мала']:
            return word[:-3] + 'ів'
    
    if lower.endswith('ева') and len(word) > 4:
        return word[:-3] + 'ів'
    
    # -ада/-яда -> -ад/-яд (Павлограда -> Павлоград)
    if lower.endswith('ада') and len(word) > 4:
        return word[:-1]
    
    if lower.endswith('яда') and len(word) > 4:
        return word[:-1]
    
    # -ополя -> -опіль (Мелітополя -> Мелітополь)
    if lower.endswith('ополя'):
        return word[:-2] + 'ль'
    
    # -ополю -> -опіль (Мелітополю -> Мелітополь)
    if lower.endswith('ополю'):
        return word[:-2] + 'ль'
    
    # -пра -> -про (Дніпра -> Дніпро)
    if lower.endswith('пра') and len(word) > 4:
        return word[:-1] + 'о'
    
    # -ки -> -ка (Софіївки -> Софіївка)
    if lower.endswith('ки') and len(word) > 3:
        return word[:-1] + 'а'
    
    # -ого -> -е (Синельникового -> Синельникове)
    if lower.endswith('ого') and len(word) > 4:
        return word[:-3] + 'е'
    
    # Rules for accusative -> nominative
    # -ку -> -ка (Васильківку -> Васильківка)
    if lower.endswith('ку') and len(word) > 3:
        return word[:-1] + 'а'
    
    # -ну -> -на (Просяну -> Просяна)
    if lower.endswith('ну') and len(word) > 3:
        return word[:-1] + 'а'
    
    # -лю -> -ля (Хотімлю -> Хотімля)
    if lower.endswith('лю') and len(word) > 3:
        return word[:-1] + 'я'
    
    # -гу -> -га
    if lower.endswith('гу') and len(word) > 3:
        return word[:-1] + 'а'
    
    # -ом -> без окончания (Павлоградом -> Павлоград, Харковом -> Харків)
    if lower.endswith('ом') and len(word) > 4:
        base = word[:-2]
        # Check if base ends with consonant
        if base and base[-1].lower() in 'бвгджзклмнпрстфхцчшщ':
            return base
    
    # -і/-ові -> remove (у Павлограді -> Павлоград, в Харкові -> Харків)
    if lower.endswith('ові') and len(word) > 5:
        return word[:-3]
    
    if lower.endswith('і') and len(word) > 3:
        # Check if it's locative case (ends with -ові, -аді, -ді, etc.)
        if lower.endswith('аді') or lower.endswith('яді'):
            return word[:-2] + 'д'
        # Generic -і removal for other locative cases
        base = word[:-1]
        if base and base[-1].lower() in 'вджклмнпрстфхцчшщ':
            return base
    
    # Capitalize first letter
    if word and word[0].islower():
        word = word[0].upper() + word[1:]
    
    return word


def normalize_region(region: str) -> Optional[str]:
    """
    Normalize region name to standard format "Назва обл."
    
    Handles:
    - Colloquial names (Харківщина -> Харківська обл.)
    - Duplicate "обл обл." fixes
    - Missing periods
    
    Args:
        region: Raw region name
        
    Returns:
        Normalized region or None
    """
    if not region:
        return None
    
    region = region.strip()
    
    # Check alias mapping first
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
    """
    Extract region from text containing regional alias.
    
    Args:
        text: Text that may contain region alias (e.g., "Харківщина")
        
    Returns:
        Normalized region or None
    """
    for alias, region in REGION_ALIASES.items():
        if alias.lower() in text.lower():
            return region
    return None


def is_skip_word(word: str) -> bool:
    """Check if word should be skipped (not a real location)."""
    return word.lower() in SKIP_WORDS
