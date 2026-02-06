"""Tests for geocoding utilities."""
import pytest

from utils.geo import get_region_for_city, geocode_city_sync


def test_get_region_for_city_known_cities():
    """get_region_for_city returns correct region for known cities."""
    assert get_region_for_city("Харків") == "Харківська обл."
    assert get_region_for_city("Київ") == "Київська обл."
    assert get_region_for_city("Одеса") == "Одеська обл."
    assert get_region_for_city("Суми") == "Сумська обл."
    assert get_region_for_city("Чернігів") == "Чернігівська обл."
    assert get_region_for_city("Богодухів") == "Харківська обл."


def test_get_region_for_city_case_insensitive():
    """CITY_TO_REGION lookup is case-insensitive."""
    assert get_region_for_city("харків") == "Харківська обл."
    assert get_region_for_city("КИЇВ") == "Київська обл."


def test_get_region_for_city_with_hint():
    """Hint is returned when city not in CITIES or cache."""
    result = get_region_for_city("UnknownCity123", hint="Харківська обл.")
    assert result == "Харківська обл."


def test_get_region_for_city_empty():
    """Empty city returns None."""
    assert get_region_for_city("") is None


def test_geocode_city_sync_known():
    """geocode_city_sync returns from CITIES for known cities."""
    assert geocode_city_sync("Харків") == "Харківська обл."
    assert geocode_city_sync("Суми") == "Сумська обл."


def test_geocode_city_sync_hint():
    """geocode_city_sync returns hint for unknown city (no API)."""
    result = geocode_city_sync("UnknownCity456", hint_region="Сумська обл.")
    assert result == "Сумська обл."


def test_geocode_city_sync_short_city():
    """Very short city names return None."""
    assert geocode_city_sync("ab") is None
