
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


def _read_player(conn, player_id: int) -> MainPlayer | None:
    """Читает героя через существующее соединение."""

    row = conn.execute("""
        SELECT id, name, race, class_name, level,
               stats, passives, hp_now
        FROM players
        WHERE id = ?
    """, (player_id,)).fetchone()

    if row is None:
        return None

    data = dict(row)
    data["stats"] = json.loads(data["stats"])
    data["passives"] = json.loads(data["passives"])

    return MainPlayer(**data)


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
                passives TEXT NOT NULL DEFAULT '[]',
                hp_now INTEGER CHECK (hp_now >= 0),
                username TEXT COLLATE NOCASE UNIQUE
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


def migrate_player_hp(db_path: Path = DB_PATH):
    """Добавляет текущее HP без изменения существующих героев."""

    with closing(_connect(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")

        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(players)")
        }

        if not columns:
            raise ValueError("Таблица players не найдена")

        if "hp_now" not in columns:
            conn.execute("""
                ALTER TABLE players
                ADD COLUMN hp_now INTEGER CHECK (hp_now >= 0)
            """)


def migrate_player_usernames(db_path: Path = DB_PATH):
    """Добавляет username к существующим героям."""

    with closing(_connect(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")

        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(players)")
        }

        if not columns:
            raise ValueError("Таблица players не найдена")

        if "username" not in columns:
            conn.execute("""
                ALTER TABLE players
                ADD COLUMN username TEXT COLLATE NOCASE
            """)

        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_players_username
            ON players(username COLLATE NOCASE)
        """)


def get_player(
    player_id: int,
    db_path: Path = DB_PATH,
) -> MainPlayer | None:
    with closing(_connect(db_path)) as conn:
        return _read_player(conn, player_id)



def create_player(
    player_id: int,
    name: str,
    db_path: Path = DB_PATH,
) -> MainPlayer:
    """Создаёт игрока с нулевыми базовыми характеристиками."""

    from .catalog import load_character_catalog

    if "lvl1up" not in load_character_catalog("passives"):
        raise ValueError("Пассивка lvl1up не найдена")

    with closing(_connect(db_path)) as conn, conn:
        conn.execute(
            """
            INSERT INTO players (id, name, stats, passives)
            VALUES (?, ?, ?, ?)
            """,
            (
                player_id,
                name,
                DEFAULT_STATS_JSON,
                json.dumps(["lvl1up"]),
            ),
        )

    return get_player(player_id, db_path)

def _choice_passive(kind: str, code: str) -> str:
    """Получает пассивку из каталога расы или класса."""

    from .catalog import load_character_catalog

    if kind not in ("races", "classes") or not isinstance(code, str):
        raise ValueError("Некорректный выбор")

    entity = load_character_catalog(kind).get(code)

    if entity is None:
        raise ValueError(f"Неизвестная сущность: {kind}/{code}")

    passive_id = entity.get("passive")

    if (
        not isinstance(passive_id, str)
        or passive_id not in load_character_catalog("passives")
    ):
        raise ValueError(
            f"Неизвестная пассивка для {kind}/{code}"
        )

    return passive_id


def _set_choice_with_passive(
    player_id: int,
    code: str,
    kind: str,
    db_path: Path,
) -> bool:
    """Сохраняет выбор и пассивку одной транзакцией."""

    rules = {
        "races": (
            "race",
            "race IS NULL AND class_name IS NULL",
        ),
        "classes": (
            "class_name",
            "race IS NOT NULL AND class_name IS NULL",
        ),
    }

    if kind not in rules:
        raise ValueError("Неизвестный тип выбора")

    passive_id = _choice_passive(kind, code)
    column, condition = rules[kind]

    with closing(_connect(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute(
            f"""
            SELECT passives
            FROM players
            WHERE id = ? AND {condition}
            """,
            (player_id,),
        ).fetchone()

        if row is None:
            return False

        passives = json.loads(row["passives"])

        if passive_id not in passives:
            passives.append(passive_id)

        conn.execute(
            f"""
            UPDATE players
            SET {column} = ?, passives = ?
            WHERE id = ? AND {condition}
            """,
            (
                code,
                json.dumps(passives, ensure_ascii=False),
                player_id,
            ),
        )

    return True

def set_race_and_class(
    player_id: int,
    race: str,
    class_name: str,
    db_path: Path = DB_PATH,
) -> MainPlayer:
    """Назначает расу, класс и соответствующие пассивки."""

    from .catalog import load_character_catalog

    races = load_character_catalog("races")
    classes = load_character_catalog("classes")
    passives_catalog = load_character_catalog("passives")

    if race not in races:
        raise ValueError("Неизвестная раса")

    if class_name not in classes:
        raise ValueError("Неизвестный класс")

    race_passive = races[race]["passive"]
    class_passive = classes[class_name]["passive"]

    if (
        race_passive not in passives_catalog
        or class_passive not in passives_catalog
    ):
        raise ValueError("Неизвестная пассивка")

    with closing(_connect(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute(
            """
            SELECT race, class_name, passives
            FROM players
            WHERE id = ?
            """,
            (player_id,),
        ).fetchone()

        if row is None:
            raise ValueError("Игрок не найден")

        if row["race"] is not None or row["class_name"] is not None:
            raise ValueError("Раса или класс уже выбраны")

        passives = json.loads(row["passives"])

        for passive_id in (race_passive, class_passive):
            if passive_id not in passives:
                passives.append(passive_id)

        conn.execute(
            """
            UPDATE players
            SET race = ?, class_name = ?, passives = ?
            WHERE id = ?
            """,
            (
                race,
                class_name,
                json.dumps(passives, ensure_ascii=False),
                player_id,
            ),
        )

    return get_player(player_id, db_path)


def set_race(
    player_id: int,
    race: str,
    db_path: Path = DB_PATH,
) -> bool:
    """Назначает расу и её пассивку."""

    return _set_choice_with_passive(
        player_id, race, "races", db_path
    )


def set_class(
    player_id: int,
    class_name: str,
    db_path: Path = DB_PATH,
) -> bool:
    """Назначает класс и его пассивку."""

    return _set_choice_with_passive(
        player_id, class_name, "classes", db_path
    )


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


def set_hp_now(
    player_id: int,
    hp_now: int,
    db_path: Path = DB_PATH,
) -> bool:
    """Устанавливает текущее HP героя."""

    if type(hp_now) is not int or hp_now < 0:
        raise ValueError("Некорректное значение HP")

    with closing(_connect(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")

        player = _read_player(conn, player_id)

        if player is None:
            raise ValueError("Игрок не найден")

        maximum = player.hp_max

        if maximum is None:
            raise ValueError("Герой ещё не выбрал класс")

        if hp_now > maximum:
            raise ValueError("HP не может превышать максимум")

        if player.hp_now == hp_now:
            return False

        conn.execute(
            "UPDATE players SET hp_now = ? WHERE id = ?",
            (hp_now, player_id),
        )

    return True


def remember_player_username(
    player_id: int,
    username: str | None,
    db_path: Path = DB_PATH,
) -> bool:
    """Обновляет Telegram username существующего героя."""

    with closing(_connect(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")

        exists = conn.execute(
            "SELECT 1 FROM players WHERE id = ?",
            (player_id,),
        ).fetchone()

        if exists is None:
            return False

        # Username может перейти к другому аккаунту.
        if username is not None:
            conn.execute("""
                UPDATE players
                SET username = NULL
                WHERE username = ? COLLATE NOCASE
                  AND id <> ?
            """, (username, player_id))

        conn.execute(
            "UPDATE players SET username = ? WHERE id = ?",
            (username, player_id),
        )

    return True


def find_player_id_by_username(
    username: str,
    db_path: Path = DB_PATH,
) -> int | None:
    """Ищет Telegram ID по сохранённому username."""

    with closing(_connect(db_path)) as conn:
        row = conn.execute("""
            SELECT id
            FROM players
            WHERE username = ? COLLATE NOCASE
        """, (username,)).fetchone()

    return row["id"] if row is not None else None


def delete_player(
    player_id: int,
    db_path: Path = DB_PATH,
) -> bool:
    """Безвозвратно удаляет героя и данные создания."""

    with closing(_connect(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")

        result = conn.execute(
            "DELETE FROM players WHERE id = ?",
            (player_id,),
        )

        conn.execute(
            "DELETE FROM creation_prompts WHERE user_id = ?",
            (player_id,),
        )

    return result.rowcount > 0


if __name__ == "__main__":
    init_db()
    print(f"База готова: {DB_PATH}")
