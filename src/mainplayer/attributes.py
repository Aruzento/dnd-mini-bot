"""Базовые и итоговые характеристики героя."""

from .catalog import load_character_catalog

ABILITIES = (
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
)
BASE_DEFENSE = 10


def default_stats() -> dict[str, int]:
    return {ability: 0 for ability in ABILITIES}


def calculate_stats(
    base_stats: dict[str, int],
    passives: list[str],
) -> dict[str, int]:
    """Суммирует базовые значения и бонусы активных пассивок."""

    if (
        set(base_stats) != set(ABILITIES)
        or any(type(v) is not int for v in base_stats.values())
    ):
        raise ValueError("Некорректные базовые характеристики")

    if (
        any(not isinstance(code, str) for code in passives)
        or len(set(passives)) != len(passives)
    ):
        raise ValueError("Некорректный список пассивок")

    catalog = load_character_catalog("passives")
    result = base_stats.copy()

    for code in passives:
        if code not in catalog:
            raise ValueError(f"Неизвестная пассивка: {code}")

        bonuses = catalog[code].get("stats")

        if not isinstance(bonuses, dict):
            raise ValueError(f"Некорректные бонусы пассивки: {code}")

        for ability, bonus in bonuses.items():
            if ability not in ABILITIES or type(bonus) is not int:
                raise ValueError(
                    f"Некорректный бонус: {code}/{ability}"
                )

            result[ability] += bonus

    return result


def calculate_max_hp(
    level: int,
    constitution: int,
    class_modifier: int,
) -> int:
    """Максимальное HP с учётом уровня и телосложения."""

    if type(level) is not int or level < 1:
        raise ValueError("Некорректный уровень")

    if (
        type(constitution) is not int
        or type(class_modifier) is not int
    ):
        raise ValueError("Некорректные параметры HP")

    return class_modifier + constitution * level


def calculate_defense(
    dexterity: int,
    character_bonus: int = 0,
) -> int:
    """Защита с учётом ловкости и бонусов отряда."""

    if (
        type(dexterity) is not int
        or type(character_bonus) is not int
    ):
        raise ValueError("Некорректные параметры защиты")

    return BASE_DEFENSE + dexterity + character_bonus
