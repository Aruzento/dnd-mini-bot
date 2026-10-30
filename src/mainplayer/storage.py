
import sqlite3
import json
from .attributes import ABILITIES, default_stats
from contextlib import closing
from pathlib import Path

from .model import MainPlayer


DB_PATH = Path("/srv/mini_utl/db/mini.db")
DEFAULT_STATS_JSON = json.dumps(
    default_stats(),
    separators=(",", ":"),
)


def _connect(db_path: Path):
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DB_PATH):
    """Создаёт новую таблицу. Старую структуру не меняет."""

    with closing(_connect(db_path)) as conn, conn:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
                    CHECK (length(trim(name)) > 0),
                race TEXT,
                class_name TEXT,
                level INTEGER NOT NULL DEFAULT 1
                    CHECK (level >= 1),
                stats TEXT NOT NULL DEFAULT '{DEFAULT_STATS_JSON}',
                passives TEXT NOT NULL DEFAULT '[]'
            )
        """)

def migrate_player_stats(db_path: Path = DB_PATH):
    """Совместимая миграция после резервного копирования БД."""

    with closing(_connect(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")

        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(players)")
        }

        if not columns:
            raise ValueError("Таблица players не найдена")

        if "stats" not in columns:
            conn.execute(
                f"ALTER TABLE players ADD COLUMN "
                f"stats TEXT NOT NULL DEFAULT '{DEFAULT_STATS_JSON}'"
            )

        if "passives" not in columns:
            conn.execute(
                "ALTER TABLE players ADD COLUMN "
                "passives TEXT NOT NULL DEFAULT '[]'"
            )

def get_player(
    player_id: int,
    db_path: Path = DB_PATH,
) -> MainPlayer | None:

    with closing(_connect(db_path)) as conn:
        row = conn.execute("""
            SELECT id, name, race, class_name, level, stats, passives
            FROM players
            WHERE id = ?
        """, (player_id,)).fetchone()

    if row is None:
        return None

    data = dict(row)
    data["stats"] = json.loads(data["stats"])
    data["passives"] = json.loads(data["passives"])

    return MainPlayer(**data)


def create_player(
    player_id: int,
    name: str,
    db_path: Path = DB_PATH
) -> MainPlayer:
    """Создаёт нового игрока."""
    with closing(_connect(db_path)) as conn, conn:
        conn.execute(
            "INSERT INTO players (id, name) VALUES (?, ?)",
            (player_id, name)
        )

    return get_player(player_id, db_path)


def set_race_and_class(
    player_id: int,
    race: str,
    class_name: str,
    db_path: Path = DB_PATH
) -> MainPlayer:
    """Сохраняет выбор расы и класса."""
    with closing(_connect(db_path)) as conn, conn:
        result = conn.execute(
            """
            UPDATE players
            SET race = ?, class_name = ?
            WHERE id = ?
            """,
            (race, class_name, player_id)
        )

        if result.rowcount != 1:
            raise ValueError("Игрок не найден")

    return get_player(player_id, db_path)


def set_race(
    player_id: int,
    race: str,
    db_path: Path = DB_PATH
) -> bool:
    """Сохраняет расу один раз, во время регистрации."""
    with closing(_connect(db_path)) as conn, conn:
        result = conn.execute(
            """
            UPDATE players
            SET race = ?
            WHERE id = ?
              AND race IS NULL
              AND class_name IS NULL
            """,
            (race, player_id)
        )
        return result.rowcount == 1


def set_class(
    player_id: int,
    class_name: str,
    db_path: Path = DB_PATH
) -> bool:
    """Сохраняет класс после выбора расы."""
    with closing(_connect(db_path)) as conn, conn:
        result = conn.execute(
            """
            UPDATE players
            SET class_name = ?
            WHERE id = ?
              AND race IS NOT NULL
              AND class_name IS NULL
            """,
            (class_name, player_id)
        )
        return result.rowcount == 1

def _update_player_json(player_id, column, mutate, db_path):
    """Атомарно изменяет JSON-поле героя."""

    if column not in {"stats", "passives"}:
        raise ValueError("Неизвестное поле")

    with closing(_connect(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute(
            f"SELECT {column} FROM players WHERE id = ?",
            (player_id,),
        ).fetchone()

        if row is None:
            raise ValueError("Игрок не найден")

        value = json.loads(row[column])

        if not mutate(value):
            return False

        conn.execute(
            f"UPDATE players SET {column} = ? WHERE id = ?",
            (json.dumps(value, ensure_ascii=False), player_id),
        )

    return True


def set_base_stat(
    player_id: int,
    ability: str,
    score: int,
    db_path: Path = DB_PATH,
) -> bool:
    """Изменяет базовую характеристику."""

    if ability not in ABILITIES or type(score) is not int or score < 0:
        raise ValueError("Некорректная характеристика или значение")

    def change(stats):
        if stats[ability] == score:
            return False

        stats[ability] = score
        return True

    return _update_player_json(player_id, "stats", change, db_path)


def add_passive(
    player_id: int,
    passive_id: str,
    db_path: Path = DB_PATH,
) -> bool:
    """Добавляет пассивку, если её ещё нет."""

    from .catalog import load_character_catalog

    if passive_id not in load_character_catalog("passives"):
        raise ValueError("Неизвестная пассивка")

    def change(passives):
        if passive_id in passives:
            return False

        passives.append(passive_id)
        return True

    return _update_player_json(player_id, "passives", change, db_path)


def remove_passive(
    player_id: int,
    passive_id: str,
    db_path: Path = DB_PATH,
) -> bool:
    """Удаляет пассивку героя."""

    def change(passives):
        if passive_id not in passives:
            return False

        passives.remove(passive_id)
        return True

    return _update_player_json(player_id, "passives", change, db_path)

if __name__ == "__main__":
    init_db()
    print(f"База готова: {DB_PATH}")
