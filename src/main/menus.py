"""Read a small, editable JSON menu on each request."""

import json
import re
from pathlib import Path

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from src.mainplayer.catalog import load_character_catalog

MENU_DIR = Path(__file__).resolve().parents[2] / "catalogs" / "menu"


def _read_menu_data(name: str) -> dict:
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", name):
        raise ValueError(f"Invalid menu name: {name}")

    with (MENU_DIR / f"{name}.json").open(
        encoding="utf-8"
    ) as file:
        return json.load(file)


def load_menu_image(name: str) -> str | None:
    """Возвращает Telegram file_id изображения меню."""
    data = _read_menu_data(name)
    image = data.get("image")

    if image is None:
        return None

    if not isinstance(image, dict):
        raise ValueError(f"Invalid image in menu: {name}")

    file_id = image.get("file_id")

    if file_id is None:
        return None

    if not isinstance(file_id, str) or not file_id.strip():
        raise ValueError(f"Invalid image file_id: {name}")

    return file_id


def load_menu(
    name: str,
    player=None
) -> tuple[str, InlineKeyboardMarkup | None]:
    """Return menu text and its keyboard; read the JSON every time."""
    data = _read_menu_data(name)

    text = data["text"]
    buttons = data["buttons"]
    if not isinstance(text, str) or not text.strip() or not isinstance(buttons, list):
        raise ValueError(f"Invalid JSON menu: {name}")

    # Данные героя подставляем только в профиль
    if name == "profile" and player is not None:
        races = load_character_catalog("races")
        classes = load_character_catalog("classes")

        text = text.format(
            name=player.name,
            level=player.level,
            race=races[player.race]["name"],
            class_name=classes[player.class_name]["name"],
        )

    columns = data.get("columns", 1)

    if type(columns) is not int or not 1 <= columns <= 8:
        raise ValueError(f"Invalid columns in menu: {name}")

    # Автоматически формируем выбор из игрового каталога
    options = data.get("options_from")

    if options is not None:
        if not isinstance(options, dict):
            raise ValueError("Некорректные options_from")

        kind = options["catalog"]
        prefix = options["callback_prefix"]

        if not isinstance(prefix, str) or not prefix:
            raise ValueError("Некорректный callback_prefix")

        catalog = load_character_catalog(kind)

        descriptions = []

        for code, entity in catalog.items():
            description = entity.get("description", "")

            if description:
                descriptions.append(
                    f"{entity['name']} — {description}"
                )

        text = text.replace(
            "{descriptions}",
            "\n".join(descriptions),
        )

        buttons = buttons + [
            {
                "text": entity["name"],
                "callback_data": f"{prefix}{code}",
            }
            for code, entity in catalog.items()
        ]


    rows = []
    for button in buttons:
        if not isinstance(button, dict):
            raise ValueError(f"Invalid button in {name}")
        label = button["text"]
        action = button["callback_data"]
        if not isinstance(label, str) or not label.strip() or not isinstance(action, str):
            raise ValueError(f"Invalid button in {name}")
        if not 1 <= len(action.encode("utf-8")) <= 64:
            raise ValueError(f"Invalid callback size in {name}")
        if not rows or len(rows[-1]) == columns:
            rows.append([])

        rows[-1].append(
            InlineKeyboardButton(
                text=label,
                callback_data=action,
            )
        )

    return text, InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
