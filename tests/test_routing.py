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


def test_route_count_na_city_with_region_header():
    text = "Чернігівщина:\n▪️2 на Богодухів"
    events = route_message(text, "test")
    assert events
    assert events[0].type == ThreatType.BPLA
    assert events[0].city == "Богодухів"


def test_route_arrow_multi_cities():
    text = "Чернігівщина:\n→Короп/Бахмач(2х)"
    events = route_message(text, "test")
    cities = {e.city for e in events}
    assert "Короп" in cities
    assert "Бахмач" in cities


def test_route_launch_message():
    text = "Пуски БПЛА з Приморсько-Ахтарська"
    events = route_message(text, "test")
    assert events
    assert events[0].type == ThreatType.LAUNCH
    assert "Пуск РФ (" in events[0].format_message()


def test_route_recon():
    text = "Розвідувальний БПЛА курсом на Київ (Київська обл.)"
    events = route_message(text, "test")
    assert events
    assert events[0].type == ThreatType.RECON
    assert events[0].city == "Київ"
    assert "Разведка" in events[0].format_message()


def test_format_explosion_unified():
    events = route_message("Київ - вибухи", "test")
    assert events
    msg = events[0].format_message()
    assert msg.startswith("Вибухи ")
    assert "Київ" in msg
