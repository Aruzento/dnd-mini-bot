import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.mainplayer.model import MainPlayer
from src.mainplayer.storage import (
    migrate_player_hp,
    add_passive,
    create_player,
    get_player,
    init_db,
    migrate_player_stats,
    remove_passive,
    set_base_stat,
    migrate_all,
)
from src.mainplayer.attributes import (
    calculate_defense,
    calculate_max_hp,
)


class AttributesTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "mini.db"
        init_db(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_new_hero(self):
        player = create_player(123, "Ренкай", self.path)

        self.assertEqual(
            player,
            MainPlayer(
                id=123,
                name="Ренкай",
                passives=["lvl1up"],
            ),
        )

        self.assertTrue(all(v == 0 for v in player.stats.values()))
        self.assertTrue(all(v == 1 for v in player.effective_stats.values()))

    def test_passives_stack_remove_and_persist(self):
        create_player(123, "Ренкай", self.path)

        for code in ("elf_passive", "wizard_passive", "lvl4up"):
            self.assertTrue(add_passive(123, code, self.path))

        self.assertFalse(add_passive(123, "elf_passive", self.path))

        player = get_player(123, self.path)

        self.assertEqual(player.stats["dexterity"], 0)
        self.assertEqual(player.effective_stats["dexterity"], 4)
        self.assertEqual(player.effective_stats["intelligence"], 3)

        self.assertTrue(remove_passive(123, "elf_passive", self.path))
        self.assertFalse(remove_passive(123, "elf_passive", self.path))

        player = get_player(123, self.path)
        self.assertEqual(player.effective_stats["dexterity"], 2)

    def test_change_base_does_not_change_bonuses(self):
        create_player(123, "Ренкай", self.path)

        self.assertTrue(
            set_base_stat(123, "dexterity", 14, self.path)
        )
        self.assertTrue(add_passive(123, "elf_passive", self.path))

        player = get_player(123, self.path)

        self.assertEqual(player.stats["dexterity"], 14)
        self.assertEqual(player.effective_stats["dexterity"], 17)

    def test_unknown_passive(self):
        create_player(123, "Ренкай", self.path)

        with self.assertRaises(ValueError):
            add_passive(123, "unknown", self.path)

        self.assertEqual(
            get_player(123, self.path).passives,
            ["lvl1up"],
        )

    def test_legacy_migration(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute("DROP TABLE players")
            conn.execute("""
                CREATE TABLE players (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    race TEXT,
                    class_name TEXT,
                    level INTEGER NOT NULL DEFAULT 1
                )
            """)
            conn.execute("""
                INSERT INTO players (id, name, race, level)
                VALUES (123, 'Ренкай', 'elf', 4)
            """)

        migrate_all(self.path)
        migrate_all(self.path)

        with sqlite3.connect(self.path) as conn:
            columns = {
                row[1]
                for row in conn.execute(
                    "PRAGMA table_info(players)"
                )
            }

        self.assertTrue(
            {"stats", "passives", "hp_now", "username"}
            <= columns
        )

        player = get_player(123, self.path)

        self.assertEqual(player.level, 4)
        self.assertEqual(player.race, "elf")
        self.assertEqual(player.stats["strength"], 0)
        self.assertEqual(player.passives, [])
        self.assertIsNone(player.hp_now)

    
    def test_hp_and_defense_formulas(self):
        self.assertEqual(
            calculate_max_hp(4, 2, 5),
            13,
        )

        self.assertEqual(
            calculate_defense(3, 2),
            15,
        )

        self.assertEqual(
            calculate_defense(3),
            13,
        )

    def test_hp_and_defense_use_passives(self):
        player = MainPlayer(
            id=123,
            name="Ренкай",
            level=4,
            passives=[
                "lvl1up",
                "elf_passive",
                "fighter_passive",
            ],
        )

        self.assertEqual(
            player.effective_stats["constitution"],
            2,
        )
        self.assertEqual(
            player.effective_stats["dexterity"],
            3,
        )

        self.assertEqual(player.max_hp(5), 13)
        self.assertEqual(player.defense(2), 15)

        # Удаление пассивки изменяет итоговые значения.
        player.passives.remove("fighter_passive")

        self.assertEqual(player.max_hp(5), 9)
        self.assertEqual(player.defense(2), 15)

        # Исходные характеристики не изменяются.
        self.assertEqual(player.stats["constitution"], 0)

    def test_invalid_combat_parameters(self):
        with self.assertRaises(ValueError):
            calculate_max_hp(0, 2, 5)

        with self.assertRaises(ValueError):
            calculate_max_hp(4, 2, True)

        with self.assertRaises(ValueError):
            calculate_defense(3, True)
