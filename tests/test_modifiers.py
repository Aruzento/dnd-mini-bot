
"""Тесты математического ядра D&D."""

import unittest

from src.mechanics.modifiers import (
    ability_score,
    ability_modifier,
    proficiency_bonus,
    calculate_max_hp,
    calculate_defense,
    initiative_bonus,
    group_initiative_bonus,
    attack_roll_bonus,
    attack_hits,
    damage_total,
    load_variables,
)


class ModifierTests(unittest.TestCase):

    def test_variable_registry(self):
        variables = load_variables()

        self.assertEqual(
            variables["DEX"]["target"],
            "stats.dexterity",
        )
        self.assertEqual(
            variables["HP"]["target"],
            "hp.max",
        )

    def test_ability_modifiers(self):
        examples = {
            8: -1,
            10: 0,
            11: 0,
            12: 1,
            14: 2,
            16: 3,
            20: 5,
        }

        for score, expected in examples.items():
            with self.subTest(score=score):
                self.assertEqual(
                    ability_modifier(score), expected
                )

        self.assertEqual(ability_score(4), 14)

    def test_proficiency(self):
        self.assertEqual(proficiency_bonus(1), 2)
        self.assertEqual(proficiency_bonus(4), 2)
        self.assertEqual(proficiency_bonus(5), 3)
        self.assertEqual(proficiency_bonus(9), 4)
        self.assertEqual(proficiency_bonus(13), 5)
        self.assertEqual(proficiency_bonus(17), 6)

    def test_hp(self):
        self.assertEqual(calculate_max_hp(1, 0, 6), 6)
        self.assertEqual(calculate_max_hp(4, 0, 10), 28)
        self.assertEqual(calculate_max_hp(4, 1, 10), 32)

    def test_defense_and_initiative(self):
        self.assertEqual(calculate_defense(2), 12)
        self.assertEqual(calculate_defense(2, 3), 15)
        self.assertEqual(initiative_bonus(2), 2)
        self.assertEqual(
            group_initiative_bonus([1, 2, 3]), 2
        )

    def test_attack(self):
        bonus = attack_roll_bonus(
            ability=3,
            proficiency=2,
        )

        self.assertEqual(bonus, 5)

        # Равенство с AC означает попадание.
        self.assertTrue(attack_hits(10, 15, bonus))

        # Натуральные 1 и 20.
        self.assertFalse(attack_hits(1, 5, bonus))
        self.assertTrue(attack_hits(20, 30, bonus))

        self.assertFalse(attack_hits(9, 15, bonus))

    def test_damage(self):
        self.assertEqual(damage_total(6, 3), 9)
        self.assertEqual(damage_total(6, 3, 2), 11)
        self.assertEqual(damage_total(1, -3), 0)

    def test_invalid_values(self):
        with self.assertRaises(ValueError):
            ability_modifier(0)

        with self.assertRaises(ValueError):
            proficiency_bonus(0)

        with self.assertRaises(ValueError):
            group_initiative_bonus([])

        with self.assertRaises(ValueError):
            attack_hits(21, 15)
