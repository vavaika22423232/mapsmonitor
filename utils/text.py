"""
Text utilities - common text processing functions.
"""
import re
from typing import Optional


def clean_text(text: str) -> str:
    """
    Clean text from common noise.
    
    Removes:
    - Excessive whitespace
    - Common separator characters
    """
    if not text:
        return ""
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def extract_count(text: str) -> Optional[int]:
    """
    Extract count/quantity from text.
    
    Handles formats:
    - "3х БПЛА" -> 3
    - "2 шахеди" -> 2
    - "(5х)" -> 5
    
    Args:
        text: Text containing quantity
        
    Returns:
        Extracted count or None
    """
    if not text:
        return None
    
    # Try prefix format "Nх" or "N "
    match = re.match(r'^(\d+)\s*х?\s*', text)
    if match:
        return int(match.group(1))
    
    # Try parentheses format "(Nх)"
    match = re.search(r'\((\d+)х?\)', text)
    if match:
        return int(match.group(1))
    
    return None


def truncate(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to max length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def is_cyrillic(text: str) -> bool:
    """Check if text contains Cyrillic characters."""
    return bool(re.search(r'[а-яіїєґА-ЯІЇЄҐ]', text))


def remove_emoji(text: str) -> str:
    """Remove emoji from text."""
    # Common Telegram emoji
    emoji_pattern = re.compile(
        r'[💥🛸🛵⚠️❗️🔴🚀✈️👁️📡🇺🇦➡️⬅️↗️↘️↖️↙️⬆️⬇️💣🧨⚪️▪️•]',
        flags=re.UNICODE
    )
    return emoji_pattern.sub('', text)


def normalize_apostrophe(text: str) -> str:
    """Normalize different apostrophe characters."""
    if not text:
        return text
    
    # Replace various apostrophes with standard one
    return text.replace('\u02bc', "'").replace('ʼ', "'").replace('`', "'").replace('’', "'")
