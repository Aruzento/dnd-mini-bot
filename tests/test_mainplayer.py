
"""Тесты главного героя и его характеристик."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.mainplayer.model import MainPlayer
from src.mainplayer.storage import (
    set_base_stat,
    create_player,
    get_player,
    init_db,
    set_hp_now,
    set_race_and_class,
)


class MainPlayerTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_class_hp_modifiers(self):
        expected_hp = {
            "fighter": 28,
            "rogue": 23,
            "wizard": 18,
            "bard": 23,
        }

        for class_id, expected in expected_hp.items():
            with self.subTest(class_id=class_id):
                player = MainPlayer(
                    id=123,
                    name="Герой",
                    class_name=class_id,
                    level=4,
                    passives=["lvl1up"],
                )

                self.assertEqual(player.hp_max, expected)

    def test_ability_scores_and_modifiers(self):
        create_player(123, "Ренкай", self.db_path)

        player = set_race_and_class(
            123, "elf", "fighter", self.db_path
        )

        self.assertEqual(
            player.effective_stats["dexterity"], 3
        )
        self.assertEqual(
            player.ability_scores["dexterity"], 13
        )
        self.assertEqual(
            player.ability_modifiers["dexterity"], 1
        )

        self.assertEqual(
            player.ability_scores["constitution"], 12
        )
        self.assertEqual(
            player.ability_modifiers["constitution"], 1
        )

        self.assertEqual(player.proficiency_bonus, 2)
        self.assertEqual(player.initiative_bonus, 1)
        self.assertEqual(player.defense(), 11)
        self.assertEqual(player.hp_max, 11)

    def test_hp_recalculates_after_stat_change(self):
        create_player(123, "Тест", self.db_path)

        set_race_and_class(
            123, "tiefling", "wizard", self.db_path
        )

        player = get_player(123, self.db_path)

        # CON = 11, модификатор 0.
        self.assertEqual(player.hp_max, 6)
        self.assertEqual(player.current_hp, 6)

        set_base_stat(
            123, "constitution", 10, self.db_path
        )

        player = get_player(123, self.db_path)

        # CON = 21, модификатор +5.
        self.assertEqual(
            player.effective_stats["constitution"], 11
        )
        self.assertEqual(
            player.ability_scores["constitution"], 21
        )
        self.assertEqual(
            player.ability_modifiers["constitution"], 5
        )

        self.assertEqual(player.hp_max, 11)
        self.assertEqual(player.current_hp, 11)

        # Сохраняем фактическое здоровье после урона.
        set_hp_now(123, 9, self.db_path)

        set_base_stat(
            123, "constitution", 12, self.db_path
        )

        player = get_player(123, self.db_path)

        # CON = 23, модификатор +6.
        self.assertEqual(player.hp_max, 12)
        self.assertEqual(player.current_hp, 9)

    def test_tiefling_wizard_starting_hp(self):
        create_player(123, "Тест", self.db_path)

        player = set_race_and_class(
            123, "tiefling", "wizard", self.db_path
        )

        self.assertEqual(
            player.effective_stats["constitution"], 1
        )
        self.assertEqual(player.hp_max, 6)
        self.assertEqual(player.current_hp, 6)

    def test_hp_persistence(self):
        create_player(123, "Ренкай", self.db_path)

        player = set_race_and_class(
            123, "elf", "fighter", self.db_path
        )

        self.assertEqual(player.hp_max, 11)
        self.assertIsNone(player.hp_now)
        self.assertEqual(player.current_hp, 11)

        # Герой получил 4 единицы урона.
        self.assertTrue(
            set_hp_now(123, 7, self.db_path)
        )

        player = get_player(123, self.db_path)

        self.assertEqual(player.hp_now, 7)
        self.assertEqual(player.current_hp, 7)
        self.assertEqual(player.hp_max, 11)

        # Нулевое HP тоже должно сохраняться.
        self.assertTrue(
            set_hp_now(123, 0, self.db_path)
        )

        self.assertEqual(
            get_player(123, self.db_path).current_hp,
            0,
        )

        self.assertFalse(
            set_hp_now(123, 0, self.db_path)
        )

    def test_hp_validation(self):
        create_player(123, "Ренкай", self.db_path)

        with self.assertRaises(ValueError):
            set_hp_now(123, 1, self.db_path)

        set_race_and_class(
            123, "elf", "fighter", self.db_path
        )

        # Максимальное HP равно 11.
        for invalid in (-1, True, 12, 13):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    set_hp_now(
                        123, invalid, self.db_path
                    )

        with self.assertRaises(ValueError):
            set_hp_now(999, 1, self.db_path)

    def test_create_and_get(self):
        player = create_player(
            123, "Ренкай", self.db_path
        )

        self.assertEqual(
            player,
            MainPlayer(
                id=123,
                name="Ренкай",
                passives=["lvl1up"],
            ),
        )

        self.assertEqual(
            get_player(123, self.db_path), player
        )
        self.assertIsNone(
            get_player(999, self.db_path)
        )

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
            [
                "lvl1up",
                "human_passive",
                "fighter_passive",
            ],
        )

    def test_repeated_creation_does_not_erase(self):
        create_player(123, "Ренкай", self.db_path)

        with self.assertRaises(sqlite3.IntegrityError):
            create_player(
                123, "Другой", self.db_path
            )

        self.assertEqual(
            get_player(123, self.db_path).name,
            "Ренкай",
        )

    def test_repeated_init_preserves_data(self):
        create_player(123, "Ренкай", self.db_path)
        init_db(self.db_path)

        self.assertEqual(
            get_player(123, self.db_path).name,
            "Ренкай",
        )

    def test_missing_player_cannot_be_updated(self):
        with self.assertRaises(ValueError):
            set_race_and_class(
                999, "human", "fighter", self.db_path
            )


if __name__ == "__main__":
    unittest.main()
