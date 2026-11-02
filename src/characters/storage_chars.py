
"""Владение коллекционными персонажами и слоты отряда."""

from pathlib import Path

from src.mainplayer.attributes import ABILITIES
from src.mainplayer.storage import DB_PATH, _connect
from src.characters.catalog import load_character_index
from contextlib import closing


SLOT_LABELS = {
    "tank": "ТАНК",
    "dd": "ДД",
    "heal": "ХИЛ",
    "buff": "БАФФ",
    "aoe": "АОЕ",
}


def init_party_db(db_path: Path = DB_PATH):
    """Создаёт таблицу коллекции и экипировки."""

    allowed = ", ".join(f"'{slot}'" for slot in SLOT_LABELS)

    with closing(_connect(db_path)) as conn, conn:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS player_characters (
                player_id INTEGER NOT NULL,
                character_id TEXT NOT NULL,
                slot TEXT CHECK (slot IN ({allowed})),

                PRIMARY KEY (player_id, character_id),
                UNIQUE (player_id, slot),

                FOREIGN KEY (player_id)
                    REFERENCES players(id)
                    ON DELETE CASCADE
            )
        """)


def grant_character(
    player_id: int,
    character_id: str,
    db_path: Path = DB_PATH,
) -> bool:
    """Выдаёт персонажа в коллекцию без экипировки."""

    if character_id not in load_character_index():
        raise ValueError("Неизвестный персонаж")

    with closing(_connect(db_path)) as conn, conn:
        result = conn.execute("""
            INSERT OR IGNORE INTO player_characters (
                player_id, character_id
            )
            VALUES (?, ?)
        """, (player_id, character_id))

    return result.rowcount > 0


def get_owned_characters(
    player_id: int,
    db_path: Path = DB_PATH,
) -> list[dict]:
    """Возвращает коллекцию игрока и занятые слоты."""

    with closing(_connect(db_path)) as conn:
        rows = conn.execute("""
            SELECT character_id, slot
            FROM player_characters
            WHERE player_id = ?
            ORDER BY character_id
        """, (player_id,)).fetchall()

    return [dict(row) for row in rows]


def get_party_slots(
    player_id: int,
    db_path: Path = DB_PATH,
) -> dict[str, str | None]:
    """Пять слотов: ID персонажа либо None."""

    slots = dict.fromkeys(SLOT_LABELS)

    for character in get_owned_characters(player_id, db_path):
        if character["slot"] is not None:
            slots[character["slot"]] = character["character_id"]

    return slots


def equip_character(
    player_id: int,
    slot: str,
    character_id: str,
    db_path: Path = DB_PATH,
) -> bool:
    """Надевает только полученного персонажа подходящего типа."""

    if slot not in SLOT_LABELS:
        raise ValueError("Неизвестный слот")

    character = load_character_index().get(character_id)

    if character is None:
        raise ValueError("Неизвестный персонаж")

    if character["type"] != slot:
        raise ValueError("Тип персонажа не подходит для слота")

    with closing(_connect(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")

        owned = conn.execute("""
            SELECT slot
            FROM player_characters
            WHERE player_id = ? AND character_id = ?
        """, (player_id, character_id)).fetchone()

        if owned is None:
            raise ValueError("Персонажа нет в коллекции")

        if owned["slot"] == slot:
            return False

        # Сначала снимаем прежнего персонажа со слота.
        conn.execute("""
            UPDATE player_characters
            SET slot = NULL
            WHERE player_id = ? AND slot = ?
        """, (player_id, slot))

        # Затем устанавливаем нового.
        conn.execute("""
            UPDATE player_characters
            SET slot = ?
            WHERE player_id = ? AND character_id = ?
        """, (slot, player_id, character_id))

    return True


def unequip_slot(
    player_id: int,
    slot: str,
    db_path: Path = DB_PATH,
) -> bool:
    """Освобождает слот, не удаляя персонажа из коллекции."""

    if slot not in SLOT_LABELS:
        raise ValueError("Неизвестный слот")

    with closing(_connect(db_path)) as conn, conn:
        result = conn.execute("""
            UPDATE player_characters
            SET slot = NULL
            WHERE player_id = ? AND slot = ?
        """, (player_id, slot))

    return result.rowcount > 0


def read_party_effects(conn, player_id: int):
    """Суммирует характеристики и собирает пассивки отряда."""

    stats = {ability: 0 for ability in ABILITIES}
    passives = []

    equipped = conn.execute("""
        SELECT character_id
        FROM player_characters
        WHERE player_id = ? AND slot IS NOT NULL
    """, (player_id,)).fetchall()

    if not equipped:
        return stats, passives

    catalog = load_character_index()

    for row in equipped:
        character = catalog[row["character_id"]]

        for ability, bonus in character["stats"].items():
            stats[ability] += bonus

        passives.extend(character["passives"])

    return stats, passives
