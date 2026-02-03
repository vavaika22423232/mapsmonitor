"""
Event dataclass - single source of truth for threat data.
All parsing results flow through this unified model.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import hashlib

from core.constants import ThreatType, REGIONS


@dataclass
class Event:
    """
    Unified event model for all threat types.
    
    Attributes:
        id: Unique identifier (hash of key fields)
        type: Threat classification
        city: Target city/settlement (nominative case)
        region: Oblast in format "Назва обл."
        direction: Movement direction if known
        count: Number of threats if specified
        source: Source channel name
        confidence: Parsing confidence 0.0-1.0
        raw_text: Original message text (never mutated)
        timestamp: Event creation time
    """
    type: ThreatType
    city: Optional[str] = None
    region: Optional[str] = None
    direction: Optional[str] = None
    count: Optional[int] = None
    source: str = ""
    confidence: float = 1.0
    raw_text: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    id: str = field(default="", init=False)
    
    def __post_init__(self):
        """Generate unique ID after initialization."""
        self.id = self._generate_id()
    
    def _generate_id(self) -> str:
        """Generate deterministic ID from key fields."""
        key = f"{self.type.value}|{self.city or ''}|{self.region or ''}|{self.timestamp.strftime('%Y%m%d%H%M')}"
        return hashlib.md5(key.encode()).hexdigest()[:12]
    
    @property
    def dedup_key(self) -> str:
        """Key for deduplication (city + type + time window)."""
        city_norm = (self.city or "").lower().strip()
        return f"{city_norm}_{self.type.value}"
    
    @property
    def is_valid(self) -> bool:
        """Check if event has minimum required data."""
        if self.type == ThreatType.BALLISTIC and not self.city:
            return True
        if self.type == ThreatType.LAUNCH and self.city:
            return True
        if self.region and self.region.lower().startswith('невідом'):
            return False
        if self.region and self.region not in REGIONS and self.region != 'РФ':
            return False
        # Skip if city is actually a region name
        if self.city:
            city_lower = self.city.lower()
            if 'область' in city_lower or city_lower.endswith('щина') or city_lower.endswith('ччина'):
                return False
            # Skip adjective forms (Миколаївська, Харківська, etc.)
            if city_lower.endswith('ська') or city_lower.endswith('ська'):
                return False
        return bool(self.city and self.region and self.type != ThreatType.UNKNOWN)
    
    def format_message(self) -> str:
        """Format event as output message."""
        if not self.is_valid:
            return ""
        
        if self.type == ThreatType.EXPLOSION:
            return f"{self.city} ({self.region})\nвибухи."
        
        if self.type == ThreatType.BALLISTIC:
            if 'відбій' in (self.raw_text or '').lower():
                return "Відбій загрози балістики!"
            if self.city and self.region:
                return f"Ракета {self.city} ({self.region})"
            return "Загроза балістики!"

        if self.type == ThreatType.LAUNCH:
            if self.city and self.region:
                return f"Пуск {self.city} ({self.region})"
            if self.city:
                return f"Пуск {self.city}"
            return "Пуск БПЛА"
        
        return f"{self.type.value} {self.city} ({self.region})"
    
    def __str__(self) -> str:
        return self.format_message()
    
    def __repr__(self) -> str:
        return f"Event(type={self.type.value}, city={self.city}, region={self.region}, conf={self.confidence:.2f})"
