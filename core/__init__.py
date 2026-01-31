"""Core module - Event model, constants, and caching."""
from .event import Event
from .constants import REGIONS, CITIES, REGION_ALIASES, ThreatType
from .cache import DeduplicationCache

__all__ = ['Event', 'ThreatType', 'REGIONS', 'CITIES', 'REGION_ALIASES', 'DeduplicationCache']
