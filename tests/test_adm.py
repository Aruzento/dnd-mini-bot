
import os
import tempfile
import unittest
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
