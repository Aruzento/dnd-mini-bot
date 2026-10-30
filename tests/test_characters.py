
"""Тесты каталогов коллекционных персонажей."""

import copy
import unittest

from src.characters.catalog import (
    RARITY_RULES,
    _validate_character,
    load_characters,
    load_hero_passives,
)


class CharacterCatalogTests(unittest.TestCase):

    def test_all_rarities_load(self):
        for rarity in RARITY_RULES:
            with self.subTest(rarity=rarity):
                self.assertIsInstance(
                    load_characters(rarity),
                    dict,
                )

    def test_arza_zenta(self):
        arza = load_characters("legendary")["arza_zenta"]

        self.assertEqual(arza["name"], "Арза Зента")
        self.assertEqual(arza["type"], "aoe")

        self.assertEqual(
            arza["stats"],
            {
                "intelligence": 3,
                "charisma": 3,
                "constitution": 1,
                "wisdom": 2,
            },
        )

        self.assertEqual(
            arza["passives"],
            ["mischief", "fire_projectile"],
        )

        self.assertEqual(
            arza["village"]["productivity_bonus"],
            0.15,
        )

        self.assertEqual(
            arza["obtain"],
            ["gacha", "alchemy"],
        )

    def test_passive_references(self):
        arza = load_characters("legendary")["arza_zenta"]
        passives = load_hero_passives()

        self.assertEqual(
            passives[arza["passives"][0]]["name"],
            "Шалость",
        )

        self.assertEqual(
            passives[arza["passives"][1]]["name"],
            "Огненный снаряд",
        )

    def test_invalid_stat_budget(self):
        arza = copy.deepcopy(
            load_characters("legendary")["arza_zenta"]
        )

        arza["stats"]["intelligence"] = 4

        with self.assertRaises(ValueError):
            _validate_character(
                "arza_zenta",
                arza,
                "legendary",
                load_hero_passives(),
            )

    def test_unknown_passive(self):
        arza = copy.deepcopy(
            load_characters("legendary")["arza_zenta"]
        )

        arza["passives"][0] = "nonexistent_passive"

        with self.assertRaises(ValueError):
            _validate_character(
                "arza_zenta",
                arza,
                "legendary",
                load_hero_passives(),
            )

    def test_unique_allows_three_passives(self):
        arza = copy.deepcopy(
            load_characters("legendary")["arza_zenta"]
        )

        arza["passives"].append("third_passive")

        passives = load_hero_passives()
        passives["third_passive"] = passives["mischief"].copy()

        # У уникальных нет стандартного ограничения.
        _validate_character(
            "test_unique",
            arza,
            "unique",
            passives,
        )
