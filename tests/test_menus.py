"""Unit tests. These use mocks and never access Telegram or production SQLite."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.main.menus import load_menu
from src.main.home import (
    create_launcher,
    mini_command,
    play_callback,
    player_menu,
)

class MenuCatalogTests(unittest.TestCase):
    def test_all_menus_load(self):
        text, buttons = load_menu("launcher")
        self.assertTrue(text)
        self.assertEqual(buttons.inline_keyboard[0][0].text, "Играть")

        text, buttons = load_menu("main")
        self.assertTrue(text)
        self.assertIsNone(buttons)

        text, buttons = load_menu("create")
        self.assertTrue(text)
        self.assertEqual(buttons.inline_keyboard[0][0].callback_data, "mini:create")

    def test_json_is_reloaded_without_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "main.json"
            with patch("src.main.menus.MENU_DIR", Path(temp)):
                path.write_text(json.dumps({"text": "Before", "buttons": []}))
                self.assertEqual(load_menu("main")[0], "Before")
                path.write_text(json.dumps({"text": "After", "buttons": []}))
                self.assertEqual(load_menu("main")[0], "After")

    def test_unsafe_menu_name_rejected(self):
        with self.assertRaises(ValueError):
            load_menu("../../etc/passwd")

    def test_invalid_json_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "main.json"
            path.write_text("{invalid")
            with patch("src.main.menus.MENU_DIR", Path(temp)):
                with self.assertRaises(json.JSONDecodeError):
                    load_menu("main")
    
    def test_player_selection(self):
        with patch("src.main.home.get_player", return_value=None):
            self.assertEqual(player_menu(123), "create")

        partial = SimpleNamespace(
            race=None,
            class_name=None,
        )
        with patch("src.main.home.get_player", return_value=partial):
            self.assertEqual(player_menu(123), "race")

        partial = SimpleNamespace(
            race="elf",
            class_name=None,
        )
        with patch("src.main.home.get_player", return_value=partial):
            self.assertEqual(player_menu(123), "class")

        complete = SimpleNamespace(
            race="elf",
            class_name="fighter",
        )
        with patch("src.main.home.get_player", return_value=complete):
            self.assertEqual(player_menu(123), "main")

class MenuHandlersTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.chat = SimpleNamespace(id=-1001, type="supergroup")
        self.user = SimpleNamespace(id=123)
        self.bot = SimpleNamespace(
            send_message=AsyncMock(return_value=SimpleNamespace(message_id=99)),
            edit_message_text=AsyncMock(),
            edit_ephemeral_message_text=AsyncMock(),
            get_chat_member=AsyncMock(
                return_value=SimpleNamespace(status="administrator")
            ),
            pin_chat_message=AsyncMock(),
            delete_ephemeral_message=AsyncMock(),
            delete_message=AsyncMock(),
        )

    async def test_minicreate_pins_launcher(self):
        message = SimpleNamespace(chat=self.chat, message_thread_id=2, from_user=self.user)
        await create_launcher(message, self.bot)
        self.bot.send_message.assert_awaited_once()
        self.bot.pin_chat_message.assert_awaited_once_with(
            chat_id=self.chat.id, message_id=99, disable_notification=True
        )

    async def test_minicreate_rejects_non_admin(self):
        self.bot.get_chat_member.return_value.status = "member"
        message = SimpleNamespace(chat=self.chat, message_thread_id=2, from_user=self.user)
        await create_launcher(message, self.bot)
        self.bot.send_message.assert_not_awaited()
        self.bot.pin_chat_message.assert_not_awaited()

    async def test_mini_group_is_private(self):
        message = SimpleNamespace(chat=self.chat, message_thread_id=2, from_user=self.user)
        with patch("src.main.home.get_player", return_value=None):
            await mini_command(message, self.bot)
        args = self.bot.send_message.await_args.kwargs
        self.assertEqual(args["ephemeral_message_parameters"].receiver_user_id, 123)
        self.assertEqual(args["chat_id"], -1001)
        self.assertIn("Создание", args["text"])

    async def test_public_button_private_overlay_not_public_edit(self):
        message = SimpleNamespace(
            chat=self.chat, message_thread_id=2, message_id=99,
            ephemeral_message_id=None, receiver_user=None,
        )
        callback = SimpleNamespace(
            id="callback-1", from_user=self.user, message=message,
            answer=AsyncMock(),
        )
        with patch("src.main.home.get_player", return_value=None):
            await play_callback(callback, self.bot)
        params = self.bot.send_message.await_args.kwargs["ephemeral_message_parameters"]
        self.assertEqual(params.receiver_user_id, 123)
        self.assertEqual(params.callback_query_id, "callback-1")
        self.assertFalse(params.replace_callback_query_message)
        self.bot.delete_ephemeral_message.assert_not_awaited()
        self.bot.delete_message.assert_not_awaited()
        self.bot.edit_message_text.assert_not_awaited()
        callback.answer.assert_awaited_once()

    async def test_play_opens_new_menu_and_deletes_old(self):
        message = SimpleNamespace(
            chat=self.chat,
            message_thread_id=2,
            message_id=0,
            ephemeral_message_id=45,
            receiver_user=self.user,
        )

        callback = SimpleNamespace(
            id="callback-2",
            from_user=self.user,
            message=message,
            answer=AsyncMock(),
        )

        player = SimpleNamespace(
            name="Ренкай",
            race="elf",
            class_name="fighter",
        )

        with patch("src.main.home.get_player", return_value=player):
            await play_callback(callback, self.bot)

        sent_text = self.bot.send_message.await_args.kwargs["text"]

        self.assertIn("Ренкай", sent_text)
        self.assertIn("Эльф | Воин", sent_text)

        self.assertNotIn("{name}", sent_text)
        self.assertNotIn("{race}", sent_text)
        self.assertNotIn("{class_name}", sent_text)

        # Создано новое личное меню
        self.bot.send_message.assert_awaited_once()

        params = self.bot.send_message.await_args.kwargs[
            "ephemeral_message_parameters"
        ]
        self.assertFalse(params.replace_callback_query_message)

        # Старое личное меню удалено
        self.bot.delete_ephemeral_message.assert_awaited_once_with(
            chat_id=-1001,
            receiver_user_id=123,
            ephemeral_message_id=45,
        )

        # Старое меню не редактировалось
        self.bot.edit_ephemeral_message_text.assert_not_awaited()

    async def test_another_user_cannot_control_private_menu(self):
        message = SimpleNamespace(
            chat=self.chat, message_id=0, ephemeral_message_id=45,
            receiver_user=SimpleNamespace(id=456),
        )
        callback = SimpleNamespace(
            id="callback-3", from_user=self.user, message=message,
            answer=AsyncMock(),
        )
        await play_callback(callback, self.bot)
        self.bot.edit_ephemeral_message_text.assert_not_awaited()
        self.bot.send_message.assert_not_awaited()
        self.assertTrue(callback.answer.await_args.kwargs["show_alert"])

    def test_race_buttons_from_catalog(self):
        _, keyboard = load_menu("race")

        labels = [
            button.text
            for row in keyboard.inline_keyboard
            for button in row
        ]

        self.assertEqual(len(labels), 5)
        self.assertIn("Эльф", labels)


    def test_main_menu_uses_character_catalog(self):
        player = SimpleNamespace(
            name="Ренкай",
            race="elf",
            class_name="fighter",
        )

        text, _ = load_menu("main", player=player)

        self.assertIn("Ренкай", text)
        self.assertIn("Эльф | Воин", text)


if __name__ == "__main__":
    unittest.main()
