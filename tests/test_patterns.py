from parsers.patterns import PATTERNS


def test_kab_pattern():
    text = "Авіація заходить на пуски КАБ на Харків"
    assert PATTERNS.kab["aviatsiya_kab"].search(text)


def test_rocket_pattern():
    text = "Ракета курсом на Київ"
    assert PATTERNS.rocket["raketa_kursom"].search(text)
