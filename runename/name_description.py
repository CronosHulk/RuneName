"""Application use case and the small provider contract it needs."""
from dataclasses import dataclass
from typing import Protocol

from runename.names import name_runes

CATEGORY_TITLES = {
    "ru": ("Характер и особенности", "Сильные стороны", "Движение к результату", "Тень", "Главный ресурс"),
    "uk": ("Характер і особливості", "Сильні сторони", "Рух до результату", "Тінь", "Головний ресурс"),
}
CATEGORY_KEYS = ("character", "strengths", "achievement", "shadow", "resource")


class DescriptionError(Exception):
    pass


class DescriptionProvider(Protocol):
    def describe(self, name: str, runes: tuple[dict, ...], language: str) -> dict[str, str]: ...


@dataclass(frozen=True)
class NameDescription:
    name: str
    rune_ids: tuple[str, ...]
    runes: tuple[dict, ...]
    sections: dict[str, str]
    language: str

    def message(self) -> str:
        label = "Руни" if self.language == "uk" else "Руны"
        rune_text = ", ".join(f"{r['symbol']} {r['name_ru']}" for r in self.runes)
        sections = [f"{title}\n{self.sections[key]}" for key, title in zip(CATEGORY_KEYS, CATEGORY_TITLES[self.language])]
        note = "Символічна інтерпретація за рунами." if self.language == "uk" else "Символическая интерпретация по рунам."
        return f"{self.name}\n\n{label}: {rune_text}\n\n" + "\n\n".join(sections) + f"\n\n{note}"


def describe_name(name: str, language: str, catalog: dict[str, dict], provider: DescriptionProvider) -> NameDescription:
    if language not in CATEGORY_TITLES:
        raise ValueError("Language must be ru or uk")
    display, ids = name_runes(name)
    runes = tuple(catalog[rune_id] for rune_id in ids)
    sections = provider.describe(display, runes, language)
    return NameDescription(display, ids, runes, sections, language)
