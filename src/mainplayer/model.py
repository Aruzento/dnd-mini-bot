from dataclasses import dataclass, field
from .catalog import load_character_catalog
from .attributes import (
    ABILITIES,
    calculate_defense,
    calculate_max_hp,
    calculate_stats,
    default_stats,
)
from src.mechanics.modifiers import (
    ability_modifier,
    ability_score,
    proficiency_bonus as get_proficiency_bonus,
    initiative_bonus as get_initiative_bonus,
)

@dataclass
class MainPlayer:
    id: int
    name: str
    race: str | None = None
    class_name: str | None = None
    level: int = 1

    stats: dict[str, int] = field(default_factory=default_stats)
    passives: list[str] = field(default_factory=list)
    hp_now: int | None = None
    party_stats: dict[str, int] = field(default_factory=default_stats)
    party_passives: list[str] = field(default_factory=list)

    @property
    def effective_stats(self) -> dict[str, int]:
        result = calculate_stats(self.stats, self.passives)

        for ability in ABILITIES:
            result[ability] += self.party_stats[ability]

        return result


    @property
    def ability_scores(self) -> dict[str, int]:
        """Значения характеристик по принятой шкале D&D."""

        return {
            ability: ability_score(points)
            for ability, points in self.effective_stats.items()
        }

    @property
    def ability_modifiers(self) -> dict[str, int]:
        """Модификаторы шести характеристик D&D."""

        return {
            ability: ability_modifier(score)
            for ability, score in self.ability_scores.items()
        }

    @property
    def proficiency_bonus(self) -> int:
        """Мастерство зависит от уровня главного героя."""

        return get_proficiency_bonus(self.level)

    @property
    def initiative_bonus(self) -> int:
        """Бонус к броску инициативы."""

        return get_initiative_bonus(
            self.ability_modifiers["dexterity"]
        )


    def max_hp(self, class_modifier: int) -> int:
        """Вычисляет максимальное здоровье героя."""

        return calculate_max_hp(
            level=self.level,
            constitution=self.ability_modifiers["constitution"],
            class_modifier=class_modifier,
        )

    def defense(self, character_bonus: int = 0) -> int:
        """Вычисляет защиту героя."""

        return calculate_defense(
            dexterity=self.ability_modifiers["dexterity"],
            character_bonus=character_bonus,
        )

    
    @property
    def hp_max(self) -> int | None:
        """Максимальное HP по классу и итоговому телосложению."""

        if self.class_name is None:
            return None

        classes = load_character_catalog("classes")
        game_class = classes.get(self.class_name)

        if game_class is None:
            raise ValueError("Неизвестный класс героя")

        modifier = game_class.get("hp_modifier")

        if type(modifier) is not int or modifier < 1:
            raise ValueError("Некорректный модификатор HP класса")

        return self.max_hp(modifier)

    @property
    def current_hp(self) -> int | None:
        """Фактическое HP для игровой логики и интерфейса."""

        maximum = self.hp_max

        if maximum is None:
            return None

        if self.hp_now is None:
            return maximum

        if type(self.hp_now) is not int or self.hp_now < 0:
            raise ValueError("Некорректное текущее HP")

        return min(self.hp_now, maximum)
