"""Deterministic provisional author-v1 spelling rules; no I/O."""
import unicodedata

RULES = {
    "а": ("ansuz",), "б": ("berkana",), "в": ("wunjo",), "г": ("gebo",), "ґ": ("gebo",),
    "д": ("dagaz",), "е": ("ehwaz",), "ё": ("ehwaz",), "є": ("jera", "ehwaz"),
    "ж": ("algiz",), "з": ("algiz",), "и": ("isa",), "і": ("isa",), "й": ("jera",),
    "ї": ("jera", "isa"), "к": ("kenaz",), "л": ("laguz",), "м": ("mannaz",),
    "н": ("nauthiz",), "о": ("othala",), "п": ("perthro",), "р": ("raidho",),
    "с": ("sowilo",), "т": ("tiwaz",), "у": ("uruz",), "ф": ("fehu",), "х": ("hagalaz",),
    "ц": ("sowilo",), "ч": ("kenaz", "hagalaz"), "ш": ("sowilo", "hagalaz"),
    "щ": ("sowilo", "hagalaz"), "ы": ("isa", "jera"), "э": ("eihwaz",),
    "ю": ("jera", "uruz"), "я": ("jera", "ansuz"),
    **{char: () for char in "ьъ'’ʼ- "},
}


def name_runes(name: str) -> tuple[str, tuple[str, ...]]:
    display = unicodedata.normalize("NFC", name).strip()
    if not 1 <= len(display) <= 80:
        raise ValueError("Ім’я має містити від 1 до 80 символів / Имя: от 1 до 80 символов.")
    ids = []
    for char in display.lower():
        if char not in RULES:
            raise ValueError(f"Непідтримуваний символ / Неподдерживаемый символ: {char!r}")
        ids.extend(RULES[char])
    unique = tuple(dict.fromkeys(ids))
    if not unique:
        raise ValueError("Введіть ім’я літерами / Введите имя буквами.")
    return display, unique
