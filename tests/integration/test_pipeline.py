"""Integration tests - full pipeline: normalize -> route_message -> format_message."""
import pytest

from parsers.normalize import normalize_text
from parsers.routing import route_message


def test_pipeline_bpla_with_region():
    """Full path: raw message -> normalized -> events -> formatted."""
    raw = "**БПЛА** Харків (Харківська обл.) https://t.me/x"
    normalized = normalize_text(raw)
    assert "Харків" in normalized
    assert "https" not in normalized

    events = route_message(normalized, "test")
    assert len(events) >= 1
    ev = events[0]
    assert ev.city == "Харків"
    assert ev.region == "Харківська обл."

    msg = ev.format_message()
    assert "Харків" in msg
    assert "Харківська" in msg
    assert "БПЛА" in msg


def test_pipeline_explosion():
    """Explosion message through full pipeline."""
    raw = "Київ - вибухи"
    normalized = normalize_text(raw)
    events = route_message(normalized, "test")
    assert len(events) >= 1
    assert events[0].type.value == "Вибухи"
    msg = events[0].format_message()
    assert msg.startswith("Вибухи ")
    assert "Київ" in msg


def test_pipeline_ballistic_vidbiy():
    """Ballistic all-clear through full pipeline."""
    raw = "Відбій загрози балістики"
    normalized = normalize_text(raw)
    events = route_message(normalized, "test")
    assert len(events) == 1
    msg = events[0].format_message()
    assert "відбій" in msg.lower() or "Відбій" in msg


def test_pipeline_region_header_cities():
    """Region header + city list through full pipeline."""
    raw = "Чернігівщина:\n▪️2 на Богодухів"
    normalized = normalize_text(raw)
    events = route_message(normalized, "test")
    assert len(events) >= 1
    cities = [e.city for e in events]
    assert "Богодухів" in cities


def test_pipeline_launch():
    """Launch message through full pipeline."""
    raw = "Пуски БПЛА з Приморсько-Ахтарська"
    normalized = normalize_text(raw)
    events = route_message(normalized, "test")
    assert len(events) >= 1
    msg = events[0].format_message()
    assert "Пуск" in msg or "пуск" in msg.lower()
