
"""Базовая механика бросков кубиков D&D."""

import secrets
from dataclasses import dataclass


ALLOWED_SIDES = frozenset((4, 6, 8, 10, 12, 20, 100))
MAX_DICE = 100


@dataclass(frozen=True, slots=True)
class RollResult:
    """Результат броска одного или нескольких кубиков."""

    sides: int
    rolls: tuple[int, ...]
    modifier: int = 0

    @property
    def total(self) -> int:
        """Сумма всех кубиков с учётом модификатора."""
        return sum(self.rolls) + self.modifier


def roll(
    sides: int,
    count: int = 1,
    modifier: int = 0,
) -> RollResult:
    """Бросает кубики и возвращает результат."""

    if type(sides) is not int or sides not in ALLOWED_SIDES:
        raise ValueError("Неподдерживаемый кубик")

    if type(count) is not int or not 1 <= count <= MAX_DICE:
        raise ValueError(
            f"Количество кубиков должно быть от 1 до {MAX_DICE}"
        )

    if type(modifier) is not int:
        raise ValueError("Модификатор должен быть целым числом")

    results = tuple(
        secrets.randbelow(sides) + 1
        for _ in range(count)
    )

    return RollResult(
        sides=sides,
        rolls=results,
        modifier=modifier,
    )
