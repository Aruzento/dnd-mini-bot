
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.main.creation import (
    init_creation_db,
    next_menu,
    save_prompt,
    take_prompt,
)
from src.mainplayer.storage import (
    create_player,
    get_player,
    init_db,
    set_class,
    set_race,
)


class CreationTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "mini_test.db"
        init_db(self.db)
        init_creation_db(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def test_new_player_starts_without_race(self):
        player = create_player(123, "Ренкай", self.db)
        self.assertEqual(player.name, "Ренкай")
        self.assertEqual(player.level, 1)
        self.assertIsNone(player.race)
        self.assertIsNone(player.class_name)
        self.assertEqual(next_menu(player), "race")

    def test_race_selection(self):
        create_player(123, "Ренкай", self.db)
        self.assertTrue(set_race(123, "elf", self.db))

        player = get_player(123, self.db)
        self.assertEqual(player.race, "elf")
        self.assertEqual(next_menu(player), "class")

    def test_class_selection(self):
        create_player(123, "Ренкай", self.db)
        set_race(123, "elf", self.db)
        self.assertTrue(set_class(123, "fighter", self.db))

        player = get_player(123, self.db)
        self.assertEqual(player.class_name, "fighter")
        self.assertEqual(next_menu(player), "main")

    def test_class_requires_race(self):
        create_player(123, "Ренкай", self.db)

        self.assertFalse(set_class(123, "fighter", self.db))
        self.assertIsNone(get_player(123, self.db).class_name)

    def test_repeated_buttons_do_not_change_choice(self):
        create_player(123, "Ренкай", self.db)

        self.assertTrue(set_race(123, "elf", self.db))
        self.assertFalse(set_race(123, "dwarf", self.db))

        self.assertTrue(set_class(123, "fighter", self.db))
        self.assertFalse(set_class(123, "wizard", self.db))

        player = get_player(123, self.db)
        self.assertEqual(player.race, "elf")
        self.assertEqual(player.class_name, "fighter")

    def test_duplicate_creation_preserves_player(self):
        create_player(123, "Ренкай", self.db)

        with self.assertRaises(sqlite3.IntegrityError):
            create_player(123, "Другой", self.db)

        self.assertEqual(get_player(123, self.db).name, "Ренкай")

    def test_progress_survives_new_connection(self):
        create_player(123, "Ренкай", self.db)
        set_race(123, "elf", self.db)

        # get_player открывает новое соединение SQLite
        player = get_player(123, self.db)
        self.assertEqual(next_menu(player), "class")

    def test_prompt_id_is_saved_and_consumed(self):
        message = SimpleNamespace(
            chat=SimpleNamespace(id=-1001),
            message_id=0,
            ephemeral_message_id=45,
        )

        save_prompt(message, 123, self.db)
        prompt = take_prompt(-1001, 123, self.db)

        self.assertEqual(prompt[0], 45)
        self.assertIsNone(prompt[1])
        self.assertIsNone(take_prompt(-1001, 123, self.db))

    def test_players_are_isolated(self):
        create_player(123, "Ренкай", self.db)
        create_player(456, "Другой", self.db)
        set_race(123, "elf", self.db)

        self.assertIsNone(get_player(456, self.db).race)


if __name__ == "__main__":
    unittest.main()
