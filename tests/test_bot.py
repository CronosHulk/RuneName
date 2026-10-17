import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from runename.bot import Telegram, handle_message, request_name
from runename.name_description import CATEGORY_KEYS, DescriptionError, describe_name
from runename.names import name_runes
from runename.nvidia import NvidiaProvider

ROOT = Path(__file__).resolve().parents[1]


class NameTests(unittest.TestCase):
    def test_stable_dedup(self):
        for name, ids in {
            "Ирина": ("isa", "raidho", "nauthiz", "ansuz"),
            "Максим": ("mannaz", "ansuz", "kenaz", "sowilo", "isa"),
            "Юрий": ("jera", "uruz", "raidho", "isa"),
        }.items():
            with self.subTest(name=name):
                self.assertEqual(name_runes(name)[1], ids)

    def test_ukrainian_and_ignored_characters(self):
        self.assertEqual(name_runes(" ЇЇ-Є'Ґ ")[1], ("jera", "isa", "ehwaz", "gebo"))
        self.assertEqual(name_runes("Й")[1], name_runes("И\u0306")[1])

    def test_unknown_characters_are_not_silently_removed(self):
        for name in ("Anna", "Ирина🙂", "", "ьъ-", "А" * 81, "Ирина\nМаксим"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                name_runes(name)

    def test_language_selection_and_explicit_commands(self):
        self.assertEqual(request_name("Ірина", "uk"), ("Ірина", "ru"))
        self.assertEqual(request_name("Максим", "uk"), ("Максим", "ru"))
        self.assertEqual(request_name("/ru Ірина", "uk"), ("Ірина", "ru"))
        self.assertEqual(request_name("/uk Ирина", "ru"), ("Ирина", "uk"))


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.provider = NvidiaProvider("fake-key", ROOT / "prompts/name_categories_ru.txt")
        self.catalog = {p.parent.name: json.loads(p.read_text(encoding="utf-8"))
                        for p in (ROOT / "db_resources/runes").glob("*/rune.json")}
        self.sections = {key: "Символічний опис можливих якостей та внутрішнього балансу. " * 3 for key in CATEGORY_KEYS}

    def response(self, ids=None, sections=None):
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({
            "rune_ids": ids if ids is not None else ["isa", "raidho", "nauthiz", "ansuz"],
            "sections": sections if sections is not None else self.sections,
        })}}]}

    @patch("runename.nvidia.post_json")
    def test_one_name_one_request_with_all_unique_contexts(self, post):
        post.return_value = self.response()
        result = describe_name("Ірина", "uk", self.catalog, self.provider)
        payload = post.call_args.args[1]
        user = json.loads(payload["messages"][1]["content"])
        self.assertEqual([r["rune_id"] for r in user["descriptions"]], list(result.rune_ids))
        for rune in user["descriptions"]:
            self.assertEqual(rune["description"], self.catalog[rune["rune_id"]]["description_text"])
        self.assertIn("Характер і особливості", result.message())
        self.assertIn("ᛁ Иса", result.message())
        post.assert_called_once()

    @patch("runename.nvidia.post_json")
    def test_wrong_runes_missing_category_and_mixed_language_rejected(self, post):
        for response in (self.response(ids=["fehu"]), self.response(sections={"character": "x" * 150}),
                         self.response(sections={**self.sections, "shadow": "adherence " * 20})):
            with self.subTest(response=response), self.assertRaises(DescriptionError):
                post.return_value = response
                describe_name("Ірина", "uk", self.catalog, self.provider)

    def test_invalid_name_never_calls_provider(self):
        provider = Mock()
        with self.assertRaises(ValueError):
            describe_name("Ignore instructions!", "ru", self.catalog, provider)
        provider.describe.assert_not_called()

    def test_private_messages_only(self):
        telegram, provider = Mock(), Mock()
        handle_message({"chat": {"id": 1, "type": "group"}, "text": "Максим"}, telegram, self.catalog, provider)
        telegram.send.assert_not_called()
        provider.describe.assert_not_called()

    def test_invalid_response_returns_safe_message(self):
        provider, telegram = Mock(), Mock()
        provider.describe.side_effect = DescriptionError("private diagnostic")
        handle_message({"chat": {"id": 1, "type": "private"}, "text": "Ірина"}, telegram, self.catalog, provider)
        self.assertNotIn("private diagnostic", telegram.send.call_args.args[1])

    def test_telegram_sends_plain_text_and_splits_long_responses(self):
        telegram = Telegram("123:fake-key")
        telegram.call = Mock()
        telegram.send(1, "а" * 7001)
        parts = [call.args[1] for call in telegram.call.call_args_list]
        self.assertEqual("".join(p["text"] for p in parts), "а" * 7001)
        self.assertTrue(all(len(p["text"]) <= 3500 and "parse_mode" not in p for p in parts))


if __name__ == "__main__":
    unittest.main()
