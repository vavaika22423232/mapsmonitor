from parsers.normalize import normalize_city, normalize_region, normalize_text


def test_normalize_text_strips_noise():
    raw = "**Test**\n\nhttps://example.com\n@user\n"  # markdown + url + username
    assert normalize_text(raw) == "Test"


def test_normalize_city_cases():
    assert normalize_city("Софіївки") == "Софіївка"
    assert normalize_city("Кривого Рогу") == "Кривий Ріг"


def test_normalize_region_alias():
    assert normalize_region("Харківщина") == "Харківська обл."
