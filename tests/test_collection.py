
"""Тесты просмотра коллекционных персонажей."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.characters.catalog import load_character_index
from src.main.collection import (
    _detail_content,
    _list_content,
    _overview_content,
    collection_callback,
)


class CollectionViewTests(unittest.TestCase):

    def test_collection_counter(self):
        with patch(
            "src.main.collection.get_owned_characters",
            return_value=[
                {"character_id": "arza_zenta", "slot": None},
            ],
        ):
            text, keyboard = _overview_content(123)

        total = len(load_character_index())

        self.assertIn(f"Коллекция: 1 / {total}", text)
        self.assertEqual(len(keyboard.inline_keyboard), 3)

    def test_empty_rarity(self):
        with patch(
            "src.main.collection.get_owned_characters",
            return_value=[],
        ):
            text, keyboard = _list_content(
                123, "common", 1
            )

            self.assertIn("Персонажей этой редкости пока нет.", text)
            self.assertIn("1 / 1", [
            button.text
            for row in keyboard.inline_keyboard
            for button in row
        ])

    def test_six_characters_per_page(self):
        # 14 виртуальных персонажей только для этого теста.
        characters = {
            f"hero_{i:02d}": {
                "name": f"Персонаж {i:02d}",
                "type": "aoe",
                "stats": {"intelligence": 3},
                "passives": [],
            }
            for i in range(14)
        }

        with patch(
            "src.main.collection.load_characters",
            return_value=characters,
        ), patch(
            "src.main.collection.get_owned_characters",
            return_value=[],
        ):
            for page, expected_count in (
                (1, 6), (2, 6), (3, 2)
            ):
                with self.subTest(page=page):
                    text, keyboard = _list_content(
                        123, "common", page
                    )

                    actions = [
                        button.callback_data
                        for row in keyboard.inline_keyboard
                        for button in row
                        if button.callback_data.startswith(
                            "mini:collection:detail:"
                        )
                    ]

                    self.assertEqual(
                        len(actions),
                        expected_count,
                    )
                    labels = [
                        button.text
                        for row in keyboard.inline_keyboard
                        for button in row
                    ]
                    self.assertIn(f"{page} / 3", labels)

            # На второй странице доступны обе стрелки.
            _, keyboard = _list_content(123, "common", 2)

        self.assertEqual(
            len(keyboard.inline_keyboard[3]),
            3,
        )

    def test_arza_detail(self):
        with patch(
            "src.main.collection.get_owned_characters",
            return_value=[
                {"character_id": "arza_zenta", "slot": None},
            ],
        ):
            text, keyboard = _detail_content(
                123, "legendary", 1, "arza_zenta"
            )

        self.assertIn("Арза Зента", text)
        self.assertIn("Получен", text)
        self.assertIn("Т1|И3|М2|Х3", text)
        self.assertIn("Шалость", text)
        self.assertIn("Огненный снаряд", text)
        self.assertIn("+0.15", text)

        self.assertEqual(
            keyboard.inline_keyboard[0][0].callback_data,
            "mini:collection:list:legendary:1",
        )

    def test_unknown_character(self):
        with self.assertRaises(ValueError):
            _detail_content(
                123, "legendary", 1, "unknown_hero"
            )


class CollectionHandlerTests(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.user = SimpleNamespace(id=123)
        self.message = SimpleNamespace(
            chat=SimpleNamespace(id=-1001, type="supergroup"),
            ephemeral_message_id=45,
            receiver_user=self.user,
        )
        self.bot = SimpleNamespace()

    async def test_collection_navigation(self):
        callback = SimpleNamespace(
            data="mini:profile:collection",
            from_user=self.user,
            message=self.message,
            answer=AsyncMock(),
        )

        player = SimpleNamespace(
            race="elf",
            class_name="wizard",
        )

        with patch(
            "src.main.collection.get_player",
            return_value=player,
        ), patch(
            "src.main.collection.get_owned_characters",
            return_value=[],
        ), patch(
            "src.main.collection.show_callback_menu",
            new_callable=AsyncMock,
        ) as show:
            await collection_callback(callback, self.bot)

        show.assert_awaited_once()

        content = show.await_args.kwargs["menu_content"]
        self.assertIn("Коллекция:", content[0])

    async def test_foreign_user_rejected(self):
        self.message.receiver_user = SimpleNamespace(id=999)

        callback = SimpleNamespace(
            data="mini:profile:collection",
            from_user=self.user,
            message=self.message,
            answer=AsyncMock(),
        )

        with patch(
            "src.main.collection.show_callback_menu",
            new_callable=AsyncMock,
        ) as show:
            await collection_callback(callback, self.bot)

        show.assert_not_awaited()
        self.assertTrue(
            callback.answer.await_args.kwargs["show_alert"]
        )
