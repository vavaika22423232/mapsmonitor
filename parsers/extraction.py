"""Compatibility wrapper for renamed entity_extraction module."""
from .entity_extraction import ExtractedEntity, extract_entities, get_region_for_city

__all__ = ['ExtractedEntity', 'extract_entities', 'get_region_for_city']
