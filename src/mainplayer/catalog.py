
import json
from pathlib import Path

CATALOG_DIR = (
    Path(__file__).resolve().parents[2]
    / "catalogs"
    / "mainplayer"
)

ALLOWED_CATALOGS = {"races", "classes", "passives"}


def load_character_catalog(kind: str) -> dict:
    """Загружает актуальный справочник рас или классов."""

    if kind not in ALLOWED_CATALOGS:
        raise ValueError(f"Неизвестный каталог: {kind}")

    path = CATALOG_DIR / f"{kind}.json"

    with path.open(encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict) or not data:
        raise ValueError(f"Некорректный каталог: {kind}")

    for code, entity in data.items():
        if (
            not isinstance(entity, dict)
            or not isinstance(entity.get("name"), str)
            or not entity["name"].strip()
        ):
            raise ValueError(f"Некорректная сущность: {kind}/{code}")

    return data
