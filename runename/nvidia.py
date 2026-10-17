"""NVIDIA adapter: exact catalog context, one request per name, no paid fallback."""
import json
import re
from pathlib import Path

from runename.http_json import ApiError, post_json
from runename.name_description import CATEGORY_KEYS, DescriptionError


class NvidiaProvider:
    def __init__(self, api_key: str, prompt_path: Path, timeout: int = 120):
        if not api_key.strip() or any(c.isspace() for c in api_key):
            raise ValueError("Set NVIDIA_API_KEY in .env")
        if not 1 <= timeout <= 120:
            raise ValueError("NVIDIA_TIMEOUT must be 1–120 seconds")
        self.api_key = api_key
        self.prompt = prompt_path.read_text(encoding="utf-8")
        self.uk_prompt = (prompt_path.parent / "name_categories_uk.txt").read_text(encoding="utf-8")
        self.timeout = timeout

    def describe(self, name: str, runes: tuple[dict, ...], language: str) -> dict[str, str]:
        ids = [r["id"] for r in runes]
        # The RU example is a style example; the explicit final language rule wins.
        language_rule = ("Write ALL five section values in Ukrainian ONLY. The Russian example above is structure only."
                         if language == "uk" else "Write ALL five section values in Russian ONLY, using Russian Cyrillic words exclusively. "
                         "No Latin words or Ukrainian letters (і ї є ґ). Do not mention rune IDs in prose.")
        language_rule += (" Each section must be just TWO short sentences, 150–350 characters. "
                          "Use simple fluent language. No borrowed English words. "
                          "Return the JSON object only, with rune_ids and the five sections.")
        payload = {
            "model": "nvidia/nemotron-3-super-120b-a12b", "stream": False, "max_tokens": 2600,
            "response_format": {"type": "json_object"},
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [
                {"role": "system", "content": (self.uk_prompt if language == "uk" else self.prompt) + "\n" + language_rule},
                {"role": "user", "content": json.dumps({"name": name, "rune_ids": ids,
                    "descriptions": [{"rune_id": r["id"], "description": r["description_text"]} for r in runes]}, ensure_ascii=False)},
            ],
        }
        try:
            response = post_json("https://integrate.api.nvidia.com/v1/chat/completions", payload,
                                 {"Authorization": "Bearer " + self.api_key}, self.timeout)
            choice = response["choices"][0]
            if choice["finish_reason"] != "stop":
                raise ValueError("Incomplete response")
            result = json.loads(choice["message"]["content"])
            sections = result["sections"]
            returned_ids = result["rune_ids"]
            if (not isinstance(returned_ids, list) or len(returned_ids) != len(ids)
                    or any(not isinstance(x, str) for x in returned_ids) or set(returned_ids) != set(ids)):
                raise ValueError("Rune IDs mismatch")
            if not isinstance(sections, dict) or set(sections) != set(CATEGORY_KEYS):
                raise ValueError("Missing categories")
            for text in sections.values():
                if not isinstance(text, str) or not 100 <= len(text.strip()) <= 650:
                    raise DescriptionError("Section length outside 100–650 characters")
                # Reject common foreign insertions observed in the MVP; do not silently edit LLM text.
                wrong = r"[A-Za-z\ufffd]" + (r"|[іїєґІЇЄҐ]" if language == "ru" else r"|[ыэёъЫЭЁЪ]")
                if re.search(wrong, text):
                    raise DescriptionError("Mixed-language section")
            return {key: sections[key].strip() for key in CATEGORY_KEYS}
        except ApiError as exc:
            raise DescriptionError(f"NVIDIA request failed (status={exc.status})") from None
        except (AttributeError, KeyError, IndexError, TypeError, ValueError):
            raise DescriptionError("NVIDIA unavailable or response did not pass validation") from None
