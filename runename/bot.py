"""Minimal Telegram long-polling composition root. Run: python -m runename.bot."""
import argparse
import json
import os
from pathlib import Path
import re
import time

from runename.http_json import ApiError, post_json
from runename.name_description import DescriptionError, describe_name
from runename.nvidia import NvidiaProvider

ROOT = Path(__file__).resolve().parents[1]
HELP = ("Надішліть одне ім’я українською або російською.\n"
        "Отправьте одно имя на украинском или русском.\n\n"
        "/uk Ірина — опис українською\n/ru Ирина — описание на русском\n\n"
        "Без команды описание на русском. /uk — українською. "
        "Символическая интерпретация, не характеристика личности.")


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if separator and re.fullmatch(r"[A-Z][A-Z0-9_]*", key.strip()):
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


class Telegram:
    def __init__(self, token: str):
        if not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", token):
            raise ValueError("Set TELEGRAM_BOT_TOKEN in .env (from @BotFather)")
        self._base = "https://api.telegram.org/bot" + token + "/"

    def call(self, method: str, payload: dict) -> object:
        response = post_json(self._base + method, payload, timeout=45)
        if response.get("ok") is not True or "result" not in response:
            raise ApiError(response.get("error_code"))
        return response["result"]

    def send(self, chat_id: int, text: str) -> None:
        # No parse_mode: model output and names are always plain text.
        # At most ~3800 Cyrillic characters under our contract; split defensively.
        while text:
            cut = min(len(text), 3500)
            if cut < len(text):
                boundary = text.rfind("\n", 0, cut)
                if boundary > 0:
                    cut = boundary
            self.call("sendMessage", {"chat_id": chat_id, "text": text[:cut]})
            text = text[cut:].lstrip("\n")


def request_name(text: str, telegram_language: str = "") -> tuple[str, str]:
    command, _, rest = text.partition(" ")
    if command in {"/uk", "/ru"}:
        return rest.strip(), command[1:]
    if text.startswith("/"):
        raise ValueError(HELP)
    return text, "ru"


def handle_message(message: dict, telegram: Telegram, catalog: dict, provider: NvidiaProvider) -> None:
    if message.get("chat", {}).get("type") != "private" or message.get("from", {}).get("is_bot"):
        return
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    if not text or text in {"/start", "/help", "/uk", "/ru"}:
        telegram.send(chat_id, HELP)
        return
    try:
        name, language = request_name(text, message.get("from", {}).get("language_code", ""))
        description = describe_name(name, language, catalog, provider)
        telegram.send(chat_id, description.message())
    except ValueError as exc:
        telegram.send(chat_id, str(exc))
    except DescriptionError:
        telegram.send(chat_id, "Не вдалося отримати коректний опис. Спробуйте пізніше.\n"
                               "Не удалось получить корректное описание. Попробуйте позже.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate config/catalog and Telegram getMe only")
    args = parser.parse_args()
    load_env(ROOT / ".env")
    try:
        telegram = Telegram(os.environ.get("TELEGRAM_BOT_TOKEN", ""))
        provider = NvidiaProvider(os.environ.get("NVIDIA_API_KEY", ""), ROOT / "prompts/name_categories_ru.txt",
                                  int(os.environ.get("NVIDIA_TIMEOUT", "120")))
        catalog = {p.parent.name: json.loads(p.read_text(encoding="utf-8"))
                   for p in (ROOT / "db_resources/runes").glob("*/rune.json")}
        if len(catalog) != 24:
            raise ValueError("Expected 24 runes in catalog")
        telegram.call("getMe", {})
        if args.check:
            print("Configuration, 24-rune catalog and Telegram token: OK")
            return
        webhook = telegram.call("getWebhookInfo", {})
        if not isinstance(webhook, dict) or webhook.get("url"):
            raise ValueError("Disable the existing Telegram webhook before starting long polling")
        print("RuneName is listening. Ctrl+C to stop. No user data is saved.")
        offset = None
        while True:
            try:
                updates = telegram.call("getUpdates", {"offset": offset, "timeout": 25,
                                                       "limit": 1, "allowed_updates": ["message"]})
                if not isinstance(updates, list):
                    raise ApiError()
                for update in updates:
                    # Advance in memory once even if sending fails; never regenerate on delivery retries.
                    offset = update["update_id"] + 1
                    handle_message(update.get("message", {}), telegram, catalog, provider)
            except ApiError as exc:
                if exc.status in {401, 404, 409}:
                    raise ValueError("Telegram token invalid or another bot instance is running") from None
                print("Telegram temporarily unavailable; retrying polling without regenerating a reply.")
                time.sleep(exc.retry_after)
    except (ValueError, OSError, ApiError) as exc:
        # Exception messages from our HTTP adapter are sanitized, never contain tokens/URLs.
        raise SystemExit(str(exc)) from None
    except KeyboardInterrupt:
        print("Stopped")


if __name__ == "__main__":
    main()
