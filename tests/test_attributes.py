import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.mainplayer.model import MainPlayer
from src.mainplayer.storage import (
    add_passive,
    create_player,
    get_player,
    init_db,
    migrate_player_stats,
    remove_passive,
    set_base_stat,
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

        self.assertEqual(player, MainPlayer(id=123, name="Ренкай"))
        self.assertEqual(len(player.stats), 6)
        self.assertEqual(player.passives, [])

    def test_passives_stack_remove_and_persist(self):
        create_player(123, "Ренкай", self.path)

        for code in ("elf", "mage", "lvl4up"):
            self.assertTrue(add_passive(123, code, self.path))

        self.assertFalse(add_passive(123, "elf", self.path))

        player = get_player(123, self.path)

        self.assertEqual(player.stats["dexterity"], 10)
        self.assertEqual(player.effective_stats["dexterity"], 12)
        self.assertEqual(player.effective_stats["intelligence"], 14)

        self.assertTrue(remove_passive(123, "elf", self.path))
        self.assertFalse(remove_passive(123, "elf", self.path))

        player = get_player(123, self.path)
        self.assertEqual(player.effective_stats["dexterity"], 11)

    def test_change_base_does_not_change_bonuses(self):
        create_player(123, "Ренкай", self.path)

        self.assertTrue(
            set_base_stat(123, "dexterity", 14, self.path)
        )
        self.assertTrue(add_passive(123, "elf", self.path))

        player = get_player(123, self.path)

        self.assertEqual(player.stats["dexterity"], 14)
        self.assertEqual(player.effective_stats["dexterity"], 15)

    def test_unknown_passive(self):
        create_player(123, "Ренкай", self.path)

        with self.assertRaises(ValueError):
            add_passive(123, "unknown", self.path)

        self.assertEqual(get_player(123, self.path).passives, [])

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

        migrate_player_stats(self.path)
        migrate_player_stats(self.path)

        player = get_player(123, self.path)

        self.assertEqual(player.level, 4)
        self.assertEqual(player.race, "elf")
        self.assertEqual(player.stats["strength"], 10)
        self.assertEqual(player.passives, [])