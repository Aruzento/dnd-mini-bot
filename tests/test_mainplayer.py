
import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.mainplayer.model import MainPlayer
from src.mainplayer.storage import (
    create_player,
    get_player,
    init_db,
    set_race_and_class,
)


class MainPlayerTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_and_get(self):
        player = create_player(123, "Ренкай", self.db_path)

        self.assertEqual(
            player,
            MainPlayer(
                id=123,
                name="Ренкай",
                passives=["lvl1up"],
            )
        )
        self.assertEqual(get_player(123, self.db_path), player)
        self.assertIsNone(get_player(999, self.db_path))

    def test_set_race_and_class(self):
        create_player(123, "Ренкай", self.db_path)

        player = set_race_and_class(
            123, "human", "fighter", self.db_path
        )

        self.assertEqual(player.race, "human")
        self.assertEqual(player.class_name, "fighter")
        self.assertEqual(player.level, 1)

        self.assertEqual(
            player.passives,
            ["lvl1up", "human_passive", "fighter_passive"],
        )

    def test_repeated_creation_does_not_erase(self):
        create_player(123, "Ренкай", self.db_path)

        with self.assertRaises(sqlite3.IntegrityError):
            create_player(123, "Другой", self.db_path)

        self.assertEqual(
            get_player(123, self.db_path).name,
            "Ренкай"
        )

    def test_repeated_init_preserves_data(self):
        create_player(123, "Ренкай", self.db_path)
        init_db(self.db_path)

        self.assertEqual(
            get_player(123, self.db_path).name,
            "Ренкай"
        )

    def test_missing_player_cannot_be_updated(self):
        with self.assertRaises(ValueError):
            set_race_and_class(
                999, "человек", "воин", self.db_path
            )


if __name__ == "__main__":
    unittest.main()
