"""Tests on real message fixtures - parse and verify no false positives."""
import os

import pytest

from parsers.routing import route_message
from core.event import Event


def _load_fixture_messages():
    """Load sample messages from fixtures file."""
    fixture_path = os.path.join(
        os.path.dirname(__file__), "fixtures", "sample_messages.txt"
    )
    with open(fixture_path, "r", encoding="utf-8") as f:
        content = f.read()
    blocks = content.split("\n---\n")
    messages = []
    for block in blocks:
        block = block.strip()
        if not block or block.startswith("#"):
            continue
        lines = [l for l in block.split("\n") if not l.strip().startswith("#")]
        msg = "\n".join(lines).strip()
        if msg:
            messages.append(msg)
    return messages


@pytest.fixture
def sample_messages():
    return _load_fixture_messages()


def test_parse_real_messages_all_valid(sample_messages):
    """Parse fixtures and verify events are valid, no false positives."""
    for text in sample_messages:
        events = route_message(text, "fixture_channel")
        for event in events:
            assert isinstance(event, Event)
            # Events returned should pass is_valid when they have city+region
            if event.city and event.region and event.type.value != "Невідомо":
                assert event.is_valid, f"Invalid event from: {text[:80]}... -> {event}"


def test_parse_empty_text():
    """Empty text produces no events."""
    events = route_message("", "test")
    assert events == []


def test_parse_emoji_only():
    """Emoji-only text produces no events."""
    events = route_message("➡️⬅️↗️↘️🛸✈️", "test")
    assert events == []


def test_parse_very_long_message():
    """Long message parses without error."""
    long_text = "Чернігівщина:\n" + "\n".join(
        f"▪️{i} на Богодухів" for i in range(50)
    )
    events = route_message(long_text, "test")
    # May or may not produce events, but should not crash
    assert all(isinstance(e, Event) for e in events)


def test_pseudo_location_over_mistom_filtered():
    """'БПЛА над містом' should not produce valid event."""
    events = route_message("БПЛА над містом", "test")
    valid = [e for e in events if e.is_valid]
    assert len(valid) == 0


def test_pseudo_location_over_sealom_filtered():
    """'Шахед над селом' should not produce valid event."""
    events = route_message("Шахед над селом", "test")
    valid = [e for e in events if e.is_valid]
    assert len(valid) == 0


def test_informational_planned_skipped():
    """Informational planned attack messages are skipped by dispatcher (routing may return empty)."""
    events = route_message("Запланував удар по об'єкту", "test")
    # Routing might still try to parse; validation filters
    assert len([e for e in events if e.is_valid]) == 0
