from parsers.routing import route_message
from core.constants import ThreatType


def test_route_ballistic_all_clear():
    events = route_message("Відбій загрози балістики", "test")
    assert len(events) == 1
    assert events[0].type == ThreatType.BALLISTIC


def test_route_explosion_city():
    events = route_message("Київ - вибухи", "test")
    assert events
    assert events[0].type == ThreatType.EXPLOSION
    assert events[0].city == "Київ"
