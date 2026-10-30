
"""Тесты базовой механики бросков."""

import unittest
from unittest.mock import patch

from src.mechanics.roll import roll


class RollTests(unittest.TestCase):

    @patch("src.mechanics.roll.secrets.randbelow", return_value=19)
    def test_d20(self, random_mock):
        result = roll(20)

        self.assertEqual(result.rolls, (20,))
        self.assertEqual(result.total, 20)
        random_mock.assert_called_once_with(20)

    @patch(
        "src.mechanics.roll.secrets.randbelow",
        side_effect=(3, 1, 5),
    )
    def test_multiple_dice(self, random_mock):
        result = roll(6, count=3, modifier=2)

        self.assertEqual(result.rolls, (4, 2, 6))
        self.assertEqual(result.total, 14)

    @patch("src.mechanics.roll.secrets.randbelow", return_value=0)
    def test_negative_modifier(self, random_mock):
        result = roll(20, modifier=-2)

        self.assertEqual(result.total, -1)

    def test_supported_dice(self):
        for sides in (4, 6, 8, 10, 12, 20, 100):
            with self.subTest(sides=sides):
                with patch(
                    "src.mechanics.roll.secrets.randbelow",
                    return_value=sides - 1,
                ):
                    self.assertEqual(roll(sides).total, sides)

    def test_invalid_arguments(self):
        for sides in (0, 3, -6, True, "20"):
            with self.subTest(sides=sides):
                with self.assertRaises(ValueError):
                    roll(sides)

        for count in (0, -1, 101, True, 1.5):
            with self.subTest(count=count):
                with self.assertRaises(ValueError):
                    roll(6, count=count)

        for modifier in (True, 1.5, "2"):
            with self.subTest(modifier=modifier):
                with self.assertRaises(ValueError):
                    roll(6, modifier=modifier)


if __name__ == "__main__":
    unittest.main()
