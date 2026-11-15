
"""Чистые расчёты модификаторов и базовых правил D&D."""

import json
import re
from pathlib import Path


BASE_ABILITY_SCORE = 10
BASE_DEFENSE = 10

VARIABLES_PATH = (
    Path(__file__).resolve().parents[2]
    / "catalogs"
    / "mechanics"
    / "variables.json"
)


def load_variables() -> dict:
    """Загружает реестр игровых переменных."""

    with VARIABLES_PATH.open(encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict) or not data:
        raise ValueError("Некорректный реестр переменных")

    for code, variable in data.items():
        if not isinstance(code, str) or not re.fullmatch(
            r"[A-Z][A-Z0-9_]*", code
        ):
            raise ValueError(f"Некорректный код: {code}")

        if not isinstance(variable, dict):
            raise ValueError(f"Некорректная переменная: {code}")

        for field in ("target", "label", "kind"):
            value = variable.get(field)

            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{code}: некорректное поле {field}"
                )

        if variable["kind"] not in {
            "ability", "derived", "bonus"
        }:
            raise ValueError(f"{code}: неизвестный вид переменной")

    return data


def ability_score(points: int) -> int:
    """Переводит накопленные очки Mini в значение D&D."""

    if type(points) is not int:
        raise ValueError("Очки характеристики должны быть целым числом")

    score = BASE_ABILITY_SCORE + points

    if score < 1:
        raise ValueError("Значение характеристики меньше 1")

    return score


def ability_modifier(score: int) -> int:
    """D&D: floor((характеристика - 10) / 2)."""

    if type(score) is not int or score < 1:
        raise ValueError("Некорректная характеристика")

    return (score - 10) // 2


def proficiency_bonus(level: int) -> int:
    """Бонус мастерства D&D по уровню."""

    if type(level) is not int or level < 1:
        raise ValueError("Некорректный уровень")

    # Стандартная прогрессия D&D 1–20 уровней.
    # При уровнях выше 20 пока сохраняем максимум +6.
    return min(6, 2 + (level - 1) // 4)


def calculate_max_hp(
    level: int,
    constitution: int,
    class_modifier: int,
) -> int:
    """HP по размеру кости хитов и модификатору CON.

    constitution — уже вычисленный модификатор.
    class_modifier — существующий размер кости хитов класса.
    Для новых уровней используется фиксированное среднее D&D.
    """

    if type(level) is not int or level < 1:
        raise ValueError("Некорректный уровень")

    if type(constitution) is not int:
        raise ValueError("Некорректный модификатор CON")

    if (
        type(class_modifier) is not int
        or class_modifier not in (6, 8, 10, 12)
    ):
        raise ValueError("Некорректная кость хитов")

    first_level = max(1, class_modifier + constitution)

    later_level = max(
        1,
        class_modifier // 2 + 1 + constitution,
    )

    return first_level + (level - 1) * later_level


def calculate_defense(
    dexterity: int,
    character_bonus: int = 0,
) -> int:
    """Базовый AC без брони: 10 + модификатор DEX + бонус."""

    if (
        type(dexterity) is not int
        or type(character_bonus) is not int
    ):
        raise ValueError("Некорректные параметры защиты")

    return BASE_DEFENSE + dexterity + character_bonus


def initiative_bonus(
    dexterity: int,
    extra_bonus: int = 0,
) -> int:
    """Бонус инициативы перед броском d20."""

    if type(dexterity) is not int or type(extra_bonus) is not int:
        raise ValueError("Некорректные параметры инициативы")

    return dexterity + extra_bonus


def group_initiative_bonus(
    dexterity_modifiers: list[int],
) -> int:
    """Средний модификатор DEX группы врагов с округлением вниз."""

    if (
        not isinstance(dexterity_modifiers, list)
        or not dexterity_modifiers
        or any(type(value) is not int for value in dexterity_modifiers)
    ):
        raise ValueError("Некорректная группа врагов")

    return sum(dexterity_modifiers) // len(dexterity_modifiers)


def attack_roll_bonus(
    ability: int,
    proficiency: int = 0,
    extra_bonus: int = 0,
) -> int:
    """Модификаторы для броска d20 на попадание."""

    if any(
        type(value) is not int
        for value in (ability, proficiency, extra_bonus)
    ):
        raise ValueError("Некорректные бонусы атаки")

    return ability + proficiency + extra_bonus


def attack_hits(
    d20: int,
    armor_class: int,
    bonus: int = 0,
) -> bool:
    """Проверяет попадание с натуральными 1 и 20."""

    if (
        type(d20) is not int
        or not 1 <= d20 <= 20
        or type(armor_class) is not int
        or type(bonus) is not int
    ):
        raise ValueError("Некорректные параметры атаки")

    if d20 == 1:
        return False

    if d20 == 20:
        return True

    return d20 + bonus >= armor_class


def damage_total(
    dice_total: int,
    ability: int = 0,
    extra_bonus: int = 0,
) -> int:
    """Урон после попадания; отрицательного урона нет."""

    if any(
        type(value) is not int
        for value in (dice_total, ability, extra_bonus)
    ):
        raise ValueError("Некорректные параметры урона")

    return max(0, dice_total + ability + extra_bonus)
