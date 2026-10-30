
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.main.creation import (
    choose_class,
    choose_race,
    create_button,
    create_command,
    delete_command_message,
    delete_old_prompt,
)


class CreationHandlerTests(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.user = SimpleNamespace(id=123)
        self.chat = SimpleNamespace(id=-1001, type="supergroup")
        self.message = SimpleNamespace(
            chat=self.chat,
            from_user=self.user,
            message_id=0,
            message_thread_id=2,
            ephemeral_message_id=45,
            receiver_user=self.user,
        )
        self.bot = SimpleNamespace(
            send_message=AsyncMock(),
            edit_ephemeral_message_text=AsyncMock(),
            delete_message=AsyncMock(),
            delete_ephemeral_message=AsyncMock(),
        )

    def callback(self, data):
        return SimpleNamespace(
            data=data,
            from_user=self.user,
            message=self.message,
            answer=AsyncMock(),
        )

    async def test_create_button_shows_name_prompt(self):
        callback = self.callback("mini:create")

        with patch("src.main.creation.get_player", return_value=None):
            with patch("src.main.creation.save_prompt") as save:
                await create_button(callback, self.bot)

        self.bot.edit_ephemeral_message_text.assert_awaited_once()
        save.assert_called_once_with(self.message, 123)
    async def test_create_accepts_name_formats(self):
        cases = [
            ('"Ренкай"', "Ренкай"),
            ("«Ренкай»", "Ренкай"),
            ("“Ренкай”", "Ренкай"),
            ("Ренкай", "Ренкай"),
            ("Ренкай Ночной", "Ренкай Ночной"),
        ]

        player = SimpleNamespace(
            race=None,
            class_name=None,
        )

        for raw_name, expected_name in cases:
            with self.subTest(raw_name=raw_name):
                self.bot.send_message.reset_mock()

                command = SimpleNamespace(args=raw_name)

                with patch(
                    "src.main.creation.get_player",
                    return_value=None,
                ):
                    with patch(
                        "src.main.creation.create_player",
                        return_value=player,
                    ) as create:
                        with patch(
                            "src.main.creation.delete_old_prompt",
                            new_callable=AsyncMock,
                        ):
                            await create_command(
                                self.message,
                                self.bot,
                                command,
                            )

                create.assert_called_once_with(
                    123,
                    expected_name,
                )

                self.assertIn(
                    "Выбор расы",
                    self.bot.send_message.await_args.kwargs["text"],
                )

    async def test_race_opens_class_menu(self):
        callback = self.callback("mini:race:elf")

        before = SimpleNamespace(race=None, class_name=None)
        after = SimpleNamespace(race="elf", class_name=None)

        with patch(
            "src.main.creation.get_player",
            side_effect=[before, after],
        ):
            with patch("src.main.creation.set_race") as save:
                await choose_race(callback, self.bot)

        save.assert_called_once_with(123, "elf")
        self.assertIn(
            "Выбор класса",
            self.bot.edit_ephemeral_message_text.await_args.kwargs["text"],
        )

    async def test_class_opens_main_menu(self):
        callback = self.callback("mini:class:fighter")

        before = SimpleNamespace(race="elf", class_name=None)
        after = SimpleNamespace(
            name="Ренкай",
            race="elf",
            class_name="fighter",
        )

        with patch(
            "src.main.creation.get_player",
            side_effect=[before, after],
        ):
            with patch("src.main.creation.set_class") as save:
                await choose_class(callback, self.bot)

        save.assert_called_once_with(123, "fighter")
        self.bot.edit_ephemeral_message_text.assert_awaited_once()

    async def test_foreign_menu_cannot_change_race(self):
        callback = self.callback("mini:race:elf")
        self.message.receiver_user = SimpleNamespace(id=456)

        with patch("src.main.creation.set_race") as save:
            await choose_race(callback, self.bot)

        save.assert_not_called()
        self.bot.edit_ephemeral_message_text.assert_not_awaited()

    async def test_create_command_cleans_previous_menu(self):
        command = SimpleNamespace(args='"Ренкай"')
        self.message.message_id = 99
        self.message.ephemeral_message_id = None

        player = SimpleNamespace(race=None, class_name=None)

        with patch("src.main.creation.get_player", return_value=None):
            with patch(
                "src.main.creation.create_player",
                return_value=player,
            ) as create:
                with patch(
                    "src.main.creation.delete_old_prompt",
                    new_callable=AsyncMock,
                ) as cleanup:
                    await create_command(
                        self.message, self.bot, command
                    )

        create.assert_called_once_with(123, "Ренкай")
        self.bot.delete_message.assert_awaited_once_with(
            chat_id=-1001, message_id=99
        )
        self.bot.send_message.assert_awaited_once()
        self.assertIn(
            "Выбор расы",
            self.bot.send_message.await_args.kwargs["text"],
        )
        cleanup.assert_awaited_once()

    async def test_saved_ephemeral_prompt_is_deleted(self):
        with patch(
            "src.main.creation.take_prompt",
            return_value=(45, None, int(time.time())),
        ):
            await delete_old_prompt(self.message, self.bot)

        self.bot.delete_ephemeral_message.assert_awaited_once_with(
            chat_id=-1001,
            receiver_user_id=123,
            ephemeral_message_id=45,
        )

    async def test_command_is_deleted(self):
        self.message.message_id = 99
        self.message.ephemeral_message_id = None

        await delete_command_message(self.message, self.bot)

        self.bot.delete_message.assert_awaited_once_with(
            chat_id=-1001,
            message_id=99,
        )
