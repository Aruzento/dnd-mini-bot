from dataclasses import dataclass, field

from .attributes import calculate_stats, default_stats


@dataclass
class MainPlayer:
    id: int
    name: str
    race: str | None = None
    class_name: str | None = None
    level: int = 1

    stats: dict[str, int] = field(default_factory=default_stats)
    passives: list[str] = field(default_factory=list)

    @property
    def effective_stats(self) -> dict[str, int]:
        return calculate_stats(self.stats, self.passives)