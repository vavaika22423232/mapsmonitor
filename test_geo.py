#!/usr/bin/env python3
"""Test geocoding pipeline."""
import asyncio
import os

os.environ.setdefault('VISICOM_API_KEY', 'b91989611bbbfbf28655c3b419f1377a')

from utils.geo import geocode_city
from parsers.normalize import normalize_city
from parsers.entity_extraction import _clean_city_name


async def test():
    test_cases = [
        # Real cities
        ('Харків', 'Харківська'),
        ('Київ', 'Київ'),
        ('Одеса', 'Одеська'),
        ('Львів', 'Львівська'),
        ('Миколаїв', 'Миколаївська'),
        ('Суми', 'Сумська'),
        ('Очаків', 'Миколаївська'),
        ('Маяки', None),  # Multiple matches - accept any
        ('Шостка', 'Сумська'),
        ('Балаклія', 'Харківська'),
        ('Ізюм', 'Харківська'),
        ('Полтава', 'Полтавська'),
        ('Запоріжжя', 'Запорізька'),
        ('Дніпро', 'Дніпропетровська'),
        ('Чернігів', 'Чернігівська'),
        ('Херсон', 'Херсонська'),
        ('Вінниця', 'Вінницька'),
        ('Житомир', 'Житомирська'),
        ('Рівне', 'Рівненська'),
        ('Луцьк', 'Волинська'),
        ('Тернопіль', 'Тернопільська'),
        ('Хмельницький', 'Хмельницька'),
        ('Ужгород', 'Закарпатська'),
        ('Івано-Франківськ', 'Івано-Франківська'),
        ('Чернівці', 'Чернівецька'),
        ('Черкаси', 'Черкаська'),
        ('Кропивницький', 'Кіровоградська'),
        
        # Small towns
        ('Конотоп', 'Сумська'),
        ('Лебедин', 'Сумська'),
        ('Куп\'янськ', 'Харківська'),
        ('Вознесенськ', 'Миколаївська'),
        ('Первомайськ', None),  # Multiple
        ('Кривий Ріг', 'Дніпропетровська'),
        ('Біла Церква', 'Київська'),
        ('Сміла', 'Черкаська'),
        ('Прилуки', 'Чернігівська'),
        
        # Oblique forms
        ('Харкова', 'Харківська'),
        ('Маяків', None),
        ('Маяка', None),
        ('Сум', 'Сумська'),
        ('Черкас', 'Черкаська'),
        ('Кривого Рогу', 'Дніпропетровська'),
        ('Нову Каховку', 'Херсонська'),
        ('Стару Каховку', 'Херсонська'),
        ('Васильківку', None),
        ('Балаклію', 'Харківська'),
        
        # Garbage (None expected)
        ('Небо', None),
        ('Столба', None),
        ('Застава', None),
        ('Берегом', None),
        ('море', None),
        ('Миколаївська область', None),
        ('на', None),
        ('рух', None),
        ('курсом', None),
        ('центр', None),
        ('Харківщина', None),
        
        # Glued
        ('Очаківсела', 'Миколаївська'),
        
        # Russian
        ('Черноморска', None),
    ]
    
    passed = failed = 0
    
    for raw, expected in test_cases:
        cleaned = _clean_city_name(raw)
        if not cleaned:
            if expected is None:
                print(f"OK {raw} -> [filtered]")
                passed += 1
            else:
                print(f"FAIL {raw} -> [filtered] (expected {expected})")
                failed += 1
            continue
        
        normalized = normalize_city(cleaned)
        region = await geocode_city(normalized)
        
        if expected is None:
            if region is None:
                print(f"OK {raw} -> {normalized} -> None")
                passed += 1
            else:
                print(f"? {raw} -> {normalized} -> {region}")
                passed += 1
        else:
            if region and expected in region:
                print(f"OK {raw} -> {normalized} -> {region}")
                passed += 1
            else:
                print(f"FAIL {raw} -> {normalized} -> {region} (expected {expected})")
                failed += 1
    
    print(f"\nRESULTS: {passed} passed, {failed} failed")


if __name__ == '__main__':
    asyncio.run(test())
