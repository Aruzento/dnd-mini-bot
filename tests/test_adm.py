
import os
import tempfile
import unittest
import asyncio

from src.adm.commands import (
    admin_image_photo,
    admin_image_usage,
)
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.adm.commands import admin_delete_character
from src.main.creation import init_creation_db, save_prompt
from src.mainplayer.storage import (
    create_player,
    delete_player,
    find_player_id_by_username,
    get_player,
    init_db,
    remember_player_username,
)


class AdminStorageTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "test.db"
        init_db(self.db)
        init_creation_db(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def test_username_lookup(self):
        create_player(456, "Герой", self.db)

        remember_player_username(456, "TestPlayer", self.db)

        self.assertEqual(
            find_player_id_by_username("testplayer", self.db),
            456,
        )

    def test_delete_is_permanent(self):
        create_player(456, "Герой", self.db)
        remember_player_username(456, "TestPlayer", self.db)

        prompt = SimpleNamespace(
            chat=SimpleNamespace(id=-1001),
            message_id=99,
            ephemeral_message_id=None,
        )

        save_prompt(prompt, 456, self.db)

        self.assertTrue(delete_player(456, self.db))
        self.assertIsNone(get_player(456, self.db))
        self.assertIsNone(
            find_player_id_by_username("TestPlayer", self.db)
        )
        self.assertFalse(delete_player(456, self.db))

        # После удаления можно создать героя заново.
        recreated = create_player(456, "Новый герой", self.db)
        self.assertEqual(recreated.name, "Новый герой")


class AdminCommandTests(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.message = SimpleNamespace(
            from_user=SimpleNamespace(id=123),
            chat=SimpleNamespace(
                id=-1001,
                type="supergroup",
            ),
            answer=AsyncMock(),
        )

        self.bot = SimpleNamespace(
            get_chat_member=AsyncMock(
                side_effect=[
                    SimpleNamespace(status="administrator"),
                    SimpleNamespace(
                        status="member",
                        user=SimpleNamespace(username="TestPlayer"),
                    ),
                ],
            ),
            send_message=AsyncMock(),
        )

    async def test_admin_deletes_by_username(self):
        with patch.dict(os.environ, {"MINI_ADMIN_IDS": "123"}):
            with patch(
                "src.adm.commands.find_player_id_by_username",
                return_value=456,
            ):
                with patch(
                    "src.adm.commands.delete_player",
                    return_value=True,
                ) as delete:
                    await admin_delete_character(
                        self.message,
                        self.bot,
                        SimpleNamespace(args="@TestPlayer"),
                    )

        delete.assert_called_once_with(456)
        self.bot.send_message.assert_awaited_once()

    async def test_unauthorized_cannot_delete(self):
        with patch.dict(os.environ, {"MINI_ADMIN_IDS": "999"}):
            with patch(
                "src.adm.commands.delete_player"
            ) as delete:
                await admin_delete_character(
                    self.message,
                    self.bot,
                    SimpleNamespace(args="456"),
                )

        delete.assert_not_called()
        self.bot.get_chat_member.assert_not_awaited()

    async def test_stale_username_cannot_delete(self):
        self.bot.get_chat_member.side_effect = [
            SimpleNamespace(status="administrator"),
            SimpleNamespace(
                status="member",
                user=SimpleNamespace(username="OtherPlayer"),
            ),
        ]

        with patch.dict(os.environ, {"MINI_ADMIN_IDS": "123"}):
            with patch(
                "src.adm.commands.find_player_id_by_username",
                return_value=456,
            ):
                with patch(
                    "src.adm.commands.delete_player"
                ) as delete:
                    await admin_delete_character(
                        self.message,
                        self.bot,
                        SimpleNamespace(args="@TestPlayer"),
                    )

        delete.assert_not_called()


    def make_photo(
        self,
        message_id,
        caption=None,
        album=None,
    ):
        """Тестовая фотография с двумя размерами."""

        return SimpleNamespace(
            message_id=message_id,
            from_user=self.message.from_user,
            chat=self.message.chat,
            caption=caption,
            media_group_id=album,
            photo=[
                SimpleNamespace(
                    file_id=f"small_{message_id}",
                    width=100,
                    height=100,
                    file_size=1000,
                ),
                SimpleNamespace(
                    file_id=f"large_{message_id}",
                    width=1000,
                    height=1000,
                    file_size=50000,
                ),
            ],
            answer=AsyncMock(),
        )

    async def test_admimage_single_photo(self):
        message = self.make_photo(
            10, caption="/admimage"
        )

        with patch.dict(
            os.environ,
            {"MINI_ADMIN_IDS": "123"},
        ):
            await admin_image_photo(message, self.bot)

        self.bot.send_message.assert_awaited_once()

        text = self.bot.send_message.await_args.kwargs["text"]

        self.assertEqual(text, "file_id:\nlarge_10")

    async def test_admimage_album_order(self):
        # Приходят не по порядку. Команда не на первом фото.
        photos = [
            self.make_photo(30, album="album1"),
            self.make_photo(
                20,
                caption="/admimage",
                album="album1",
            ),
            self.make_photo(25, album="album1"),
        ]

        with patch.dict(
            os.environ,
            {"MINI_ADMIN_IDS": "123"},
        ), patch(
            "src.adm.commands.ALBUM_SETTLE_SECONDS",
            0.02,
        ):
            first = asyncio.create_task(
                admin_image_photo(photos[0], self.bot)
            )

            await asyncio.sleep(0)

            await admin_image_photo(photos[1], self.bot)
            await admin_image_photo(photos[2], self.bot)

            await first

        self.bot.send_message.assert_awaited_once()

        text = self.bot.send_message.await_args.kwargs["text"]

        self.assertEqual(
            text,
            "file_id изображений:\n"
            "1. large_20\n"
            "2. large_25\n"
            "3. large_30",
        )

    async def test_admimage_unauthorized(self):
        message = self.make_photo(
            10, caption="/admimage"
        )

        with patch.dict(
            os.environ,
            {"MINI_ADMIN_IDS": "999"},
        ):
            await admin_image_photo(message, self.bot)

        self.bot.send_message.assert_not_awaited()
        self.bot.get_chat_member.assert_not_awaited()

    async def test_admimage_ignores_albums_without_command(self):
        photos = [
            self.make_photo(10, album="album2"),
            self.make_photo(11, album="album2"),
        ]

        with patch.dict(
            os.environ,
            {"MINI_ADMIN_IDS": "123"},
        ), patch(
            "src.adm.commands.ALBUM_SETTLE_SECONDS",
            0.02,
        ):
            first = asyncio.create_task(
                admin_image_photo(photos[0], self.bot)
            )

            await asyncio.sleep(0)
            await admin_image_photo(photos[1], self.bot)
            await first

        self.bot.send_message.assert_not_awaited()

    async def test_admimage_usage(self):
        with patch.dict(
            os.environ,
            {"MINI_ADMIN_IDS": "123"},
        ):
            await admin_image_usage(
                self.message,
                self.bot,
            )

        text = self.bot.send_message.await_args.kwargs["text"]
        self.assertIn("/admimage", text)