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


def default_stats() -> dict[str, int]:
    return {ability: 10 for ability in ABILITIES}


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