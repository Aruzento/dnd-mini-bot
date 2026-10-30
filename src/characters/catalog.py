
"""Каталоги коллекционных персонажей и их пассивок."""

import json
import re
from pathlib import Path

from src.mainplayer.attributes import ABILITIES


CATALOG_DIR = (
    Path(__file__).resolve().parents[2]
    / "catalogs"
    / "characters"
)

BASE_STAT_POINTS = 3

RARITY_RULES = {
    "common": {
        "color": "white",
        "multiplier": 1,
        "passive_count": 0,
    },
    "rare": {
        "color": "purple",
        "multiplier": 2,
        "passive_count": 1,
    },
    "legendary": {
        "color": "gold",
        "multiplier": 3,
        "passive_count": 2,
    },
    "mythic": {
        "color": "red",
        "multiplier": 1,
        "passive_count": 2,
    },
    "unique": {
        "color": "mithril",
        "multiplier": None,
        "passive_count": None,
    },
}


def _valid_id(value) -> bool:
    return (
        isinstance(value, str)
        and re.fullmatch(r"[a-z][a-z0-9_]*", value) is not None
    )


def _load_json(filename: str) -> dict:
    path = CATALOG_DIR / filename

    with path.open(encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Некорректный каталог: {filename}")

    return data


def load_hero_passives() -> dict:
    """Загружает общий каталог пассивок персонажей."""

    passives = _load_json("hero_passive.json")

    for passive_id, passive in passives.items():
        if not _valid_id(passive_id):
            raise ValueError(f"Некорректный ID пассивки: {passive_id}")

        if not isinstance(passive, dict):
            raise ValueError(f"Некорректная пассивка: {passive_id}")

        for field in ("name", "description", "trigger"):
            value = passive.get(field)

            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{passive_id}: некорректное поле {field}"
                )

        effect = passive.get("effect")

        if (
            not isinstance(effect, dict)
            or not isinstance(effect.get("type"), str)
            or not effect["type"].strip()
        ):
            raise ValueError(
                f"{passive_id}: некорректный эффект"
            )

        chance = passive.get("chance")

        if chance is not None and (
            type(chance) not in (int, float)
            or not 0 <= chance <= 1
        ):
            raise ValueError(
                f"{passive_id}: некорректная вероятность"
            )

        condition = passive.get("condition")

        if condition is not None and not isinstance(condition, dict):
            raise ValueError(
                f"{passive_id}: некорректное условие"
            )

    return passives


def _validate_character(
    character_id: str,
    character: dict,
    rarity: str,
    available_passives: dict,
) -> None:
    """Проверяет характеристики и ссылки на пассивки."""

    if not _valid_id(character_id):
        raise ValueError(f"Некорректный ID: {character_id}")

    if not isinstance(character, dict):
        raise ValueError(f"Некорректный персонаж: {character_id}")

    for field in ("name", "type"):
        value = character.get(field)

        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{character_id}: некорректное поле {field}"
            )

    stats = character.get("stats")

    if not isinstance(stats, dict):
        raise ValueError(
            f"{character_id}: характеристики должны быть объектом"
        )

    for ability, value in stats.items():
        if (
            ability not in ABILITIES
            or type(value) is not int
            or value < 0
        ):
            raise ValueError(
                f"{character_id}: некорректная характеристика {ability}"
            )

    rules = RARITY_RULES[rarity]
    multiplier = rules["multiplier"]

    if multiplier is not None:
        expected = BASE_STAT_POINTS * multiplier

        if sum(stats.values()) != expected:
            raise ValueError(
                f"{character_id}: нужно {expected} очков характеристик"
            )

    passive_ids = character.get("passives")

    if not isinstance(passive_ids, list):
        raise ValueError(
            f"{character_id}: passives должен быть массивом"
        )

    if (
        any(not _valid_id(code) for code in passive_ids)
        or len(set(passive_ids)) != len(passive_ids)
    ):
        raise ValueError(
            f"{character_id}: некорректные ID пассивок"
        )

    for passive_id in passive_ids:
        if passive_id not in available_passives:
            raise ValueError(
                f"{character_id}: неизвестная пассивка {passive_id}"
            )

    expected_count = rules["passive_count"]

    if (
        expected_count is not None
        and len(passive_ids) != expected_count
    ):
        raise ValueError(
            f"{character_id}: требуется {expected_count} пассивок"
        )

    village = character.get("village")

    if village is not None:
        if (
            not isinstance(village, dict)
            or type(village.get("productivity_bonus"))
            not in (int, float)
        ):
            raise ValueError(
                f"{character_id}: некорректный бонус деревни"
            )

    obtain = character.get("obtain")

    if (
        not isinstance(obtain, list)
        or any(
            not isinstance(source, str) or not source.strip()
            for source in obtain
        )
    ):
        raise ValueError(
            f"{character_id}: некорректные способы получения"
        )


def load_characters(rarity: str) -> dict:
    """Загружает персонажей указанной редкости."""

    if rarity not in RARITY_RULES:
        raise ValueError(f"Неизвестная редкость: {rarity}")

    characters = _load_json(f"{rarity}_chars.json")
    passives = load_hero_passives()

    for character_id, character in characters.items():
        _validate_character(
            character_id,
            character,
            rarity,
            passives,
        )

    return characters
