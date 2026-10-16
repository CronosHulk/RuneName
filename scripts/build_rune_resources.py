"""Build inspectable rune seed assets from the supplied PDF and vector geometry.

Requires pypdf. Run from the repository root; --check validates without rebuilding.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "db_resources" / "runes"
PDF = ROOT / "starter info" / "АНСУЗ.docx.pdf"
EDITORIAL = ROOT / "db_resources" / "editorial" / "eihwaz.md"

# Polylines, not font glyphs. One coordinate system for composition and rendering.
# The supplied chart is the visual reference; Ingwaz is disambiguated explicitly.
RUNES = [
    ("fehu", "Феху", "ᚠ", [[(30,105),(30,15)],[(30,45),(70,15)],[(30,65),(70,35)]]),
    ("uruz", "Уруз", "ᚢ", [[(25,105),(25,15),(75,40),(75,105)]]),
    ("thurisaz", "Турисаз", "ᚦ", [[(30,105),(30,15)],[(30,35),(75,60),(30,85)]]),
    ("ansuz", "Ансуз", "ᚨ", [[(30,105),(30,15)],[(30,15),(75,45)],[(30,45),(75,75)]]),
    ("raidho", "Райдо", "ᚱ", [[(30,105),(30,15)],[(30,15),(75,40),(30,65),(75,105)]]),
    ("kenaz", "Кено", "ᚲ", [[(70,15),(25,60),(70,105)]]),
    ("gebo", "Гебо", "ᚷ", [[(20,15),(80,105)],[(80,15),(20,105)]]),
    ("wunjo", "Вуньо", "ᚹ", [[(30,105),(30,15)],[(30,15),(75,40),(30,65)]]),
    ("hagalaz", "Хагалаз", "ᚺ", [[(25,15),(25,105)],[(75,15),(75,105)],[(25,35),(75,75)]]),
    ("nauthiz", "Наутиз", "ᚾ", [[(50,15),(50,105)],[(20,40),(80,75)]]),
    ("isa", "Иса", "ᛁ", [[(50,15),(50,105)]]),
    ("jera", "Йера", "ᛃ", [[(45,15),(20,45),(45,65)],[(55,55),(80,75),(55,105)]]),
    ("eihwaz", "Эйваз", "ᛇ", [[(25,80),(50,105),(50,15),(75,40)]]),
    ("perthro", "Перт", "ᛈ", [[(25,15),(25,105)],[(25,15),(50,40),(75,15)],[(25,105),(50,80),(75,105)]]),
    ("algiz", "Альгиз", "ᛉ", [[(50,15),(50,105)],[(20,20),(50,50),(80,20)]]),
    ("sowilo", "Соул", "ᛊ", [[(70,15),(25,60),(75,60),(30,105)]]),
    ("tiwaz", "Тейваз", "ᛏ", [[(50,15),(50,105)],[(20,45),(50,15),(80,45)]]),
    ("berkana", "Беркана", "ᛒ", [[(30,15),(30,105)],[(30,15),(75,37.5),(30,60),(75,82.5),(30,105)]]),
    ("ehwaz", "Эваз", "ᛖ", [[(20,105),(20,15),(50,50),(80,15),(80,105)]]),
    ("mannaz", "Манназ", "ᛗ", [[(20,105),(20,15),(80,65)],[(80,105),(80,15),(20,65)]]),
    ("laguz", "Лагуз", "ᛚ", [[(30,105),(30,15),(75,55)]]),
    ("ingwaz", "Ингуз", "ᛜ", [[(50,25),(80,60),(50,95),(20,60),(50,25)]]),
    ("dagaz", "Дагаз", "ᛞ", [[(20,15),(20,105),(80,15),(80,105),(20,15)]]),
    ("othala", "Отал", "ᛟ", [[(20,105),(75,50),(50,15),(25,50),(80,105)]]),
]
SOURCE_IDS = {name.upper(): key for key, name, _, _ in RUNES}
SOURCE_IDS["ЙЕРА"] = "jera"
HEADER = re.compile(r"([А-ЯЁ][А-ЯЁ /-]{1,30})\s*[—–-]\s*руна")
SECTION = re.compile(r"(?<!\d)([1-7])\.\s+(Характер|Стиль|Эмоции|Таланты|Теневая|Магические|Итоговый)")


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def svg(key: str, name: str, lines: list) -> str:
    segments = []
    for i, line in enumerate(lines):
        for j, (a, b) in enumerate(zip(line, line[1:])):
            segments.append(f'    <line id="{key}-s{i}-{j}" x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}"/>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 120" '
            f'role="img" aria-labelledby="{key}-title">\n'
            f'  <title id="{key}-title">{html.escape(name)}</title>\n'
            f'  <g id="{key}" fill="none" stroke="currentColor" stroke-width="5" '
            'stroke-linecap="round" stroke-linejoin="round">\n'
            + "\n".join(segments) + '\n  </g>\n</svg>\n')


def markdown(text: str) -> str:
    text = SECTION.sub(lambda m: "\n\n## " + m.group(0), text)
    for marker in ["Ведущие качества:", "Главная тема:", "Теневая сторона:",
                   "Задача развития:", "Что важно корректировать:",
                   "Для раскрытия талантов:", "Ключевой потенциал:",
                   "В сильном проявлении:", "В теневом проявлении:",
                   "Главная задача развития:", "Ключевая формула"]:
        text = text.replace(marker, "\n\n" + marker)
    text = text.replace(" ● ", "\n\n- ")
    return "\n".join(line.rstrip() for line in ("# " + text.strip()).splitlines()) + "\n"


def extract() -> dict:
    from pypdf import PdfReader

    texts = [" ".join((p.extract_text() or "").split()) for p in PdfReader(PDF).pages]
    offsets = []
    position = 0
    for text in texts:
        offsets.append((position, position + len(text)))
        position += len(text) + 1
    joined = " ".join(texts)
    headers = list(HEADER.finditer(joined))
    result: dict[str, list] = {}
    for index, match in enumerate(headers):
        start = match.start()
        end = headers[index+1].start() if index+1 < len(headers) else len(joined)
        key = SOURCE_IDS[match.group(1).strip()]
        text = joined[start:end].strip()
        pages = [i+1 for i, (a, b) in enumerate(offsets) if a < end and b > start]
        result.setdefault(key, []).append({"text": text, "pages": pages})
    if len(headers) != 25 or len(result) != 23:
        raise ValueError("Source headings changed; review the extraction before rebuilding")
    return result


def check() -> None:
    manifest = json.loads((OUT.parent / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["runes"]) == 24
    assert len({r["id"] for r in manifest["runes"]}) == 24
    for item in manifest["runes"]:
        folder = OUT / item["id"]
        record = json.loads((folder / "rune.json").read_text(encoding="utf-8"))
        description = (folder / "description.md").read_text(encoding="utf-8")
        assert len(re.findall(r"^## [1-7]\. ", description, re.M)) == 7, item["id"]
        assert record["description_text"] and record["sources"]
        document = ET.parse(folder / "rune.svg")
        lines = list(document.getroot().iter("{http://www.w3.org/2000/svg}line"))
        assert len(lines) == len(record["geometry"]["segments"]), item["id"]
        assert len({line.attrib["id"] for line in lines}) == len(lines)
        for line, segment in zip(lines, record["geometry"]["segments"]):
            coords = [float(line.attrib[a]) for a in ["x1", "y1", "x2", "y2"]]
            assert coords == segment["start"] + segment["end"]
            assert coords[:2] != coords[2:]
            assert all(5 <= coords[i] <= (95 if i % 2 == 0 else 115) for i in range(4))
        for source in record["sources"]:
            if source["type"] == "local_pdf":
                assert source["pages"] and all(1 <= p <= 48 for p in source["pages"])
        for alternate in record["alternate_descriptions"]:
            assert (folder / alternate["path"]).is_file()
    print("Validated: 24 SVG/JSON pairs, 24 seven-section descriptions, provenance and alternate descriptions.")


def build() -> None:
    extracted = extract()
    pdf_hash = hashlib.sha256(PDF.read_bytes()).hexdigest()
    cards, manifest = [], []
    for order, (key, name, symbol, lines) in enumerate(RUNES, 1):
        folder = OUT / key
        folder.mkdir(parents=True, exist_ok=True)
        occurrences = extracted.get(key, [])
        alternates = []
        if occurrences:
            description = markdown(occurrences[0]["text"])
            sources = [{"type": "local_pdf", "path": "starter info/АНСУЗ.docx.pdf",
                        "sha256": pdf_hash, "pages": occurrences[0]["pages"]}]
            origin = "source_pdf"
            for number, occurrence in enumerate(occurrences[1:], 2):
                path = f"description.source-{number}.md"
                (folder / path).write_text(markdown(occurrence["text"]), encoding="utf-8")
                alternates.append({"path": path, "source_pages": occurrence["pages"],
                                   "note": "Separate source occurrence; not merged into the primary text."})
        else:
            assert key == "eihwaz"
            description = EDITORIAL.read_text(encoding="utf-8")
            origin = "editorial_adaptation"
            sources = [
                {"type": "research", "url": "https://digital.library.leeds.ac.uk/10002/1/LSE2011.pdf",
                 "title": "Bernard Mees, The Yew Rune, Yogh and Yew (2011), pp. 53–74",
                 "supports": "Historical name and yew association; not a psychological profile."},
                {"type": "research", "url": "https://penelope.uchicago.edu/Thayer/E/Journals/Speculum/32/2/Runes_Yews_and_Magic*.html",
                 "title": "R. W. V. Elliott, Runes, Yews, and Magic (1957)",
                 "supports": "Yew, rune nomenclature and cultural context."},
                {"type": "modern_practice", "url": "https://www.rune-magick.com/pages/aettir2/05_eihwaz.htm",
                 "supports": "Modern esoteric interpretation, distinguished from historical evidence."},
            ]
        (folder / "description.md").write_text(description, encoding="utf-8")
        (folder / "rune.svg").write_text(svg(key, name, lines), encoding="utf-8")
        segments = [{"id": f"{key}-s{i}-{j}", "start": list(a), "end": list(b)}
                    for i, line in enumerate(lines) for j, (a, b) in enumerate(zip(line, line[1:]))]
        record = {"schema_version": 1, "id": key, "name_ru": name,
                  "symbol": symbol, "unicode": f"U+{ord(symbol):04X}", "futhark_order": order,
                  "description_language": "ru", "description_origin": origin,
                  "description_text": description, "sources": sources,
                  "alternate_descriptions": alternates,
                  "review_status": "pending_visual_and_editorial_review",
                  "geometry": {"view_box": [0,0,100,120], "stroke_width": 5,
                               "origin": "manually_authored_vector", "segments": segments},
                  "notes": []}
        if key == "ingwaz":
            variant_lines = [[(25,15),(75,75),(25,105)],[(75,15),(25,75),(75,105)]]
            (folder / "rune.extended.svg").write_text(svg(key+"-extended", name, variant_lines), encoding="utf-8")
            record["notes"].append("rune.svg is the diamond form ᛜ named in the PDF. rune.extended.svg reproduces the extended Ingwaz-like shape near И/Й and Ы in the chart; its label is ambiguous. No letter mapping is assigned.")
        dump(folder / "rune.json", record)
        manifest.append({"id": key, "name_ru": name, "directory": f"runes/{key}",
                         "metadata": f"runes/{key}/rune.json", "svg": f"runes/{key}/rune.svg",
                         "description": f"runes/{key}/description.md", "origin": origin})
        cards.append(f'<article><a href="runes/{key}/description.md">{(folder / "rune.svg").read_text(encoding="utf-8")}<h2>{html.escape(name)}</h2></a><p>{key} · {symbol}</p><small>{origin}</small></article>')
    dump(OUT.parent / "manifest.json", {"schema_version": 1,
         "description_language": "ru", "rune_count": 24, "source_pdf_sha256": pdf_hash,
         "letter_mapping_included": False, "runes": manifest})
    (OUT.parent / "preview.html").write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><title>RuneName — каталог рун</title><style>body{background:#f8f5ed;color:#33291e;font:16px system-ui;margin:32px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px}article{background:white;border:1px solid #d8cfba;border-radius:12px;padding:20px;text-align:center}svg{height:150px;width:125px}a{color:inherit;text-decoration:none}h2{font-size:20px}small{color:#6c6558}</style><h1>Каталог рун</h1><p>24 векторних еталони. Клік по руні відкриває опис. Накреслення потребують візуального приймання.</p><main>'+''.join(cards)+'</main></html>\n', encoding="utf-8")
    check()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    check() if args.check else build()
