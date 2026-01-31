from parsers.patterns import PATTERNS


def test_kab_pattern():
    text = "Авіація заходить на пуски КАБ на Харків"
    assert PATTERNS.kab["aviatsiya_kab"].search(text)


def test_rocket_pattern():
    text = "Ракета курсом на Київ"
    assert PATTERNS.rocket["raketa_kursom"].search(text)


def test_count_na_city_pattern():
    text = "▪️2 на Богодухів"
    assert PATTERNS.location["count_na_city"].search(text)


def test_city_to_you_pattern():
    text = "Павлоград - до вас шахед"
    assert PATTERNS.location["city_to_you"].search(text)
