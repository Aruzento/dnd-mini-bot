from dataclasses import dataclass

@dataclass
class MainPlayer:
    id: int
    name: str
    race: str | None = None
    class_name: str | None = None
    level: int = 1
