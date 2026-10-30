
import sqlite3
from contextlib import closing
from pathlib import Path

from .model import MainPlayer


DB_PATH = Path("/srv/mini_utl/db/mini.db")


def _connect(db_path: Path):
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DB_PATH):
    """Создаёт таблицу, если её ещё нет."""
    with closing(_connect(db_path)) as conn, conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
                    CHECK (length(trim(name)) > 0),
                race TEXT,
                class_name TEXT,
                level INTEGER NOT NULL DEFAULT 1
                    CHECK (level >= 1)
            )
        """)


def get_player(
    player_id: int,
    db_path: Path = DB_PATH
) -> MainPlayer | None:
    """Получает игрока из базы."""
    with closing(_connect(db_path)) as conn:
        row = conn.execute(
            """
            SELECT id, name, race, class_name, level
            FROM players
            WHERE id = ?
            """,
            (player_id,)
        ).fetchone()

    if row is None:
        return None

    return MainPlayer(**dict(row))


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


if __name__ == "__main__":
    init_db()
    print(f"База готова: {DB_PATH}")
