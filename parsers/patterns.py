"""
Centralized precompiled regex patterns.
All patterns compiled ONCE at import time for performance.
"""
import re
from typing import Pattern, Dict, Optional

# Compile flags
_FLAGS = re.IGNORECASE | re.UNICODE


def _compile(pattern: str, flags: int = _FLAGS) -> Pattern:
    """Compile regex with standard flags."""
    return re.compile(pattern, flags)


class PatternGroup:
    """Group of related patterns for a threat type."""
    
    def __init__(self, patterns: Dict[str, Pattern]):
        self._patterns = patterns
    
    def match_any(self, text: str) -> Optional[re.Match]:
        """Try all patterns, return first match."""
        for pattern in self._patterns.values():
            m = pattern.search(text)
            if m:
                return m
        return None
    
    def match_all(self, text: str) -> list:
        """Return all matches from all patterns."""
        matches = []
        for name, pattern in self._patterns.items():
            for m in pattern.finditer(text):
                matches.append((name, m))
        return matches
    
    def __getitem__(self, key: str) -> Pattern:
        return self._patterns[key]
    
    def __contains__(self, key: str) -> bool:
        return key in self._patterns


# ============================================================================
# CLEANING PATTERNS
# ============================================================================
CLEAN = PatternGroup({
    'markdown': _compile(r'\*\*|__|~~'),
    'urls': _compile(r'https?://[^\s]+'),
    'usernames': _compile(r'@\w+'),
    'emoji_only_line': _compile(r'^[➡️⬅️↗️↘️↖️↙️⬆️⬇️🇺🇦\s|]+$'),
    'skip_keywords': _compile(r'Підписатися|ППОшник|Моніторинг 24/7|Радар України'),
})


# ============================================================================
# THREAT TYPE DETECTION
# ============================================================================
THREAT_TYPE = PatternGroup({
    'bpla': _compile(r'(?:БпЛА|БПЛА|шахед|герань|мопед|балалайк|drone)', _FLAGS),
    'rocket': _compile(r'(?:ракет|калібр|крилат)', _FLAGS),
    'kab': _compile(r'(?:КАБ|кабів|бомб)', _FLAGS),
    'ballistic': _compile(r'(?:баліст|iskander)', _FLAGS),
    'explosion': _compile(r'(?:вибух|💥)', _FLAGS),
})


# ==========================================================================
# LAUNCH DETECTION (BPLA LAUNCHES)
# ==========================================================================
LAUNCH = PatternGroup({
    'keywords': _compile(
        r'(?:пуск|пуски|зафіксовано\s+пуски|фіксуються\s+пуски|попередньо\s+фіксуються\s+пуски)',
        _FLAGS
    ),
    'source_location': _compile(
        r'(?:з|із)\s+(?:ае|а/е|аеродрома|аеродрому)?\s*'
        r'([А-ЯІЇЄҐа-яіїєґ\'\-\s]+)',
        _FLAGS
    ),
    'plus_location': _compile(
        r'^[+•▪️]\s*([А-ЯІЇЄҐа-яіїєґ\'\-\s]+)\s*$',
        _FLAGS
    )
})


# ============================================================================
# CITY + REGION EXTRACTION (UNIFIED)
# ============================================================================
LOCATION = PatternGroup({
    # Format: "City (Region обл.)" - most common, highest priority
    'city_region_parens': _compile(
        r'^[💥🛸🛵⚠️❗️🔴🚀✈️\s]*'
        r'(?:БПЛА\s+)?'
        r'(.+?)\s*'
        r'\(([^)]+обл\.?)\)'
    ),

    # Format: "City (Region alias)" without обл. keyword
    'city_region_alias_parens': _compile(
        r'^[💥🛸🛵⚠️❗️🔴🚀✈️\s]*'
        r'(?:БПЛА\s+)?'
        r'(.+?)\s*'
        r'\(([^)]+(?:щина|ччина|область|обл\.?))\)'
    ),
    
    # Format: "Region: city info" (e.g., "Харківщина: 2 на Богодухів")
    'region_colon_cities': _compile(
        r'^[🛵🛸✈️📡\s]*'
        r'(\S+(?:\s+область)?):\s*'
        r'(.+)$'
    ),
    
    # Format: "N шахедів/БпЛА на City" 
    'count_threat_na_city': _compile(
        r'[•▪️\s]*'
        r'(\d+)\s*х?\s*'
        r'(?:шахед[іиів]*|БпЛА|БПЛА)\s+'
        r'(?:курсом\s+)?на\s+'
        r'([А-ЯІЇЄҐа-яіїєґ0-9\'\-\s/,]+)'
    ),

    # Format: "N на City" (when region context is known)
    'count_na_city': _compile(
        r'[•▪️\s]*'
        r'(\d+)\s*х?\s*'
        r'(?:курсом\s+)?на\s+'
        r'([А-ЯІЇЄҐа-яіїєґ0-9\'\-\s/,]+)'
    ),

    # Format: "N City" (short form under region header)
    'count_city': _compile(
        r'[•▪️\s]*'
        r'(\d+)\s*х?\s*'
        r'([А-ЯІЇЄҐа-яіїєґ0-9\'\-\s/,]+)'
    ),

    # Format: "(Фіксується) курсом на City"
    'kursom_na_city': _compile(
        r'(?:фіксується\s+)?курс(?:ом)?\s+на\s+'
        r'([А-ЯІЇЄҐа-яіїєґ\'\-\s]+)'
    ),

    # Format: "рухається/прямує/летить на City"
    'moves_to_city': _compile(
        r'(?:рухає(?:ться|ються)|прямує|прямують|летить|летять|йде|йдуть)\s+на\s+'
        r'([А-ЯІЇЄҐа-яіїєґ\'\-\s]+)'
    ),
    
    # Format: "БпЛА курсом на City"
    'bpla_kursom_na': _compile(
        r'(?:БпЛА|БПЛА|шахед[іиів]*|мопед|балалайк[аи]?|Молнія)'
        r'(?:\s+типу\s+[^\n]+?)?\s+курсом\s+на\s+'
        r'([А-ЯІЇЄҐа-яіїєґ\'\-\s]+)'
    ),
    
    # Format: "N в районі City"
    'n_v_rayoni': _compile(
        r'(\d+)\s+в\s+район[іу]?\s+'
        r'([А-ЯІЇЄҐа-яіїєґ\'\-]+)'
    ),
    
    # Format: "→City" or "→City/р-н"
    'arrow_city': _compile(
        r'^[→➡️]\s*'
        r'([А-ЯІЇЄҐа-яіїєґ\'\-\s/]+?)'
        r'(?:/(?:р-н|район|околиц[іи]))?\s*'
        r'(?:\(\d+х?\))?\s*[.!?…]*\s*$'
    ),
    
    # Format: Explosion "City - вибухи"
    'city_explosion': _compile(
        r'^[💥⚠️\s]*'
        r'([А-ЯІЇЄҐа-яіїєґ\'\-\s]+?)\s*'
        r'[-–—]\s*'
        r'(?:чули\s+)?вибух'
    ),

    # Format: "крутиться біля City" / "кружляє поблизу City"
    'threat_bilya_city': _compile(
        r'(?:[•▪️\s]*\d+\s*х?\s*)?'
        r'(?:шахед[іиів]*|БпЛА|БПЛА)?\s*'
        r'(?:крутиться|кружляє|кружляють|маневрує|маневрують)\s+'
        r'(?:біля|поблизу)\s+'
        r'([А-ЯІЇЄҐа-яіїєґ\'\-\s]+)'
    ),

    # Format: "в бік City" / "у бік City"
    'v_bik_city': _compile(
        r'(?:в|у)\s+бік\s+'
        r'([А-ЯІЇЄҐа-яіїєґ\'\-\s]+)'
    ),

    # Format: "в районі City" / "в район City"
    'v_rayoni_city': _compile(
        r'в\s+район[іу]?\s+'
        r'([А-ЯІЇЄҐа-яіїєґ\'\-\s]+)'
    ),

    # Format: "шахед над City" / "над City"
    'threat_nad_city': _compile(
        r'(?:[•▪️\s]*\d+\s*х?\s*)?'
        r'(?:шахед[іиів]*|БпЛА|БПЛА)?\s*'
        r'(?:над|над\s+містом)\s+'
        r'([А-ЯІЇЄҐа-яіїєґ\'\-\s]+)'
    ),

    # Format: "City - до вас шахед" / "City - до вас N шахеда"
    'city_to_you': _compile(
        r'^([А-ЯІЇЄҐа-яіїєґ\'\-\s]+?)\s*'
        r'[-–—]\s*'
        r'до\s+вас\s+(?:(\d+)\s+)?(?:шахед|БпЛА|БПЛА)'
    ),
    
    # Format: "City - уважно, поряд шахед" / "City - уважно"
    'city_alert': _compile(
        r'^([А-ЯІЇЄҐа-яіїєґ\'\-\s]+?)\s*'
        r'[-–—]\s*'
        r'уважно'
    ),

    # Format: "по шахеду на City"
    'po_shahedu_na': _compile(
        r'(?:по\s+)?шахед[уыуаіиів]*\s+на\s+'
        r'([А-ЯІЇЄҐа-яіїєґ\'\-\s]+)'
    ),
    
    # Format: "N шахеда біля City" without region prefix
    'count_bilya_city': _compile(
        r'^(\d+)\s+шахед[аиів]*\s+біля\s+'
        r'([А-ЯІЇЄҐа-яіїєґ\'\-\s]+)'
    ),
    
    # Format: "новий біля City" / "новий шахед біля City"
    'noviy_bilya_city': _compile(
        r'(?:новий|нові)\s+(?:шахед[іиів]*)?\s*біля\s+'
        r'([А-ЯІЇЄҐа-яіїєґ\'\-\s]+)'
    ),
    
    # Format: "останній на City" / "останній в ППУ"
    'ostanniy_na_city': _compile(
        r'останні[йі]\s+(?:на|в)\s+'
        r'([А-ЯІЇЄҐа-яіїєґ\'\-\s]+)'
    ),
    
    # Format: "повз City на другий_City" - extract destination city
    'povz_city_na': _compile(
        r'повз\s+[А-ЯІЇЄҐа-яіїєґ\'\-\s]+\s+на\s+'
        r'([А-ЯІЇЄҐа-яіїєґ\'\-\s]+)'
    ),
    
    # Format: "балалайка на City (Region)"
    'balalayka_na_city': _compile(
        r'\d+\s*(?:нова?\s+)?балалайк[аи]?\s+'
        r'(?:на\s+|підходить\s+до\s+)'
        r'([А-ЯІЇЄҐа-яіїєґ\'\-\s]+?)\s*'
        r'\(([^)]+)\)'
    ),
    
    # Format: Single city name (for context-aware parsing)
    'single_city': _compile(
        r'^([А-ЯІЇЄҐа-яіїєґ][а-яіїєґ\'\-]+)\.?\s*$'
    ),
})


# ============================================================================
# KAB-SPECIFIC PATTERNS
# ============================================================================
KAB = PatternGroup({
    # "Загроза застосування КАБів"
    'zagroza_kab': _compile(
        r'(.+?)\s*\((.+?обл\.?)\)\s*'
        r'Загроза\s+застосування\s+КАБів'
    ),
    
    # "Авіація заходить на пуски КАБ на City"
    'aviatsiya_kab': _compile(
        r'[Аа]віація\s+заходить\s+на\s+'
        r'(?:повторні\s+)?пуски\s+КАБ\s+'
        r'(?:на|в\s+напрямку)\s+'
        r'([А-ЯІЇЄҐа-яіїєґ\'\-\s/]+)'
    ),
    
    # "💣 District район (Region)"
    'kab_rayon': _compile(
        r'💣\s*(.+?)\s+район\s*\((.+?обл\.?)\)'
    ),
})


# ============================================================================
# ROCKET/BALLISTIC PATTERNS
# ============================================================================
ROCKET = PatternGroup({
    # "Ракета курсом на City"
    'raketa_kursom': _compile(
        r'(?:крилат[аі]?\s+)?ракет[аи]?\s+'
        r'(?:курсом\s+)?(?:на|в\s+напрямку)\s+'
        r'([А-ЯІЇЄҐа-яіїєґ\'\-\s]+)'
    ),
    
    # "баллистика на City"
    'ballistika_na': _compile(
        r'балл?істика\s+на\s+'
        r'([А-ЯІЇЄҐа-яіїєґ\'\-\s]+)'
    ),
    
    # "Загроза застосування балістичного озброєння"
    'zagroza_ballistyka': _compile(
        r'загроза\s+(?:застосування\s+)?балістич'
    ),
    
    # "Відбій загрози балістики"
    'vidbiy_ballistyka': _compile(
        r'відбій\s+загроз[иі]\s+(?:застосування\s+)?балістич'
    ),
    
    # "Загроза високошвидкісних цілей"
    'vysokoshvydkisni': _compile(
        r'(.+?)\s*\((.+?обл\.?)\)[\s\n]*'
        r'Загроза\s+застосування\s+високошвидкісних\s+цілей'
    ),
})


# ============================================================================
# REGION HEADER PATTERNS
# ============================================================================
REGION_HEADER = PatternGroup({
    # "Харківщина:" or "✈️Дніпропетровщина:"
    'region_header': _compile(
        r'^[✈️🛵🛸⚠️❗️🔴📡\s]*'
        r'(\S+(?:\s+область)?):?\s*$'
    ),
    
    # "4 шахеди на Чернігівщині:"
    'count_na_region': _compile(
        r'^\d+\s+(?:шахед[іиів]*|БпЛА)\s+на\s+(\S+):?\s*$'
    ),
})


# ============================================================================
# QUANTITY EXTRACTION
# ============================================================================
QUANTITY = PatternGroup({
    'prefix_count': _compile(r'^(\d+)\s*х?\s*'),
    'parens_count': _compile(r'\((\d+)х?\)'),
})


# ============================================================================
# SKIP PATTERNS (messages to ignore)
# ============================================================================
SKIP = PatternGroup({
    'alerts': _compile(r'повітряна\s+тривога|відбій\s+тривоги'),
    'shelter': _compile(r'прямуйте\s+в\s+укриття|перейдіть\s+в\s+укриття'),
    'info_only': _compile(r'На даний час \d+ БПЛА|Активність тактичної авіації'),
})


# ============================================================================
# DIRECTION WORDS (to filter out from city names)
# ============================================================================
DIRECTION_WORDS = _compile(
    r'^(?:західн|східн|північн|південн|захід|схід|північ|південь)',
    _FLAGS
)


# ============================================================================
# AGGREGATED ACCESS
# ============================================================================
class Patterns:
    """Central access point for all pattern groups."""
    clean = CLEAN
    threat_type = THREAT_TYPE
    launch = LAUNCH
    location = LOCATION
    kab = KAB
    rocket = ROCKET
    region_header = REGION_HEADER
    quantity = QUANTITY
    skip = SKIP
    direction_words = DIRECTION_WORDS


PATTERNS = Patterns()
