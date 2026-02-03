import re
pattern = re.compile(r'[🛵🛸💥⚠️❗️]\s*(\d+)\s*х?\s*(?:шахед[іиів]*|БпЛА|БПЛА|балалайк[аиів]*|мопед[іиів]*)\s+на\s+([А-ЯІЇЄҐа-яіїєґ\'\-\s]+?)[!.]*\s*$', re.IGNORECASE)
test = '🛵4х Шахеди на Вінницю!'
m = pattern.search(test)
print(f'Match: {m.groups() if m else None}')

test2 = '🛵12х Шахедів на Вінницю!!'
m2 = pattern.search(test2)
print(f'Match2: {m2.groups() if m2 else None}')
