
"""Тесты коллекции и экипировки персонажей."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from src.main.creation import init_creation_db

from src.characters.catalog import load_character_index
from src.characters.storage_chars import (
    equip_character,
    get_owned_characters,
    get_party_slots,
    grant_character,
    unequip_slot,
)
from src.main.party import party_callback
from src.mainplayer.storage import (
    create_player,
    delete_player,
    get_player,
    init_db,
    set_race_and_class,
)


class PartyTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "test.db"

        init_db(self.db)
        init_creation_db(self.db)
        create_player(123, "Герой", self.db)

    def tearDown(self):
        self.temp.cleanup()

    def test_grant_and_equip(self):
        self.assertTrue(
            grant_character(123, "arza_zenta", self.db)
        )
        self.assertFalse(
            grant_character(123, "arza_zenta", self.db)
        )

        self.assertTrue(
            equip_character(123, "aoe", "arza_zenta", self.db)
        )

        self.assertEqual(
            get_party_slots(123, self.db)["aoe"],
            "arza_zenta",
        )

        self.assertFalse(
            equip_character(123, "aoe", "arza_zenta", self.db)
        )

    def test_wrong_slot_and_missing_ownership(self):
        with self.assertRaises(ValueError):
            equip_character(123, "aoe", "arza_zenta", self.db)

        grant_character(123, "arza_zenta", self.db)

        with self.assertRaises(ValueError):
            equip_character(123, "tank", "arza_zenta", self.db)

        self.assertIsNone(get_party_slots(123, self.db)["tank"])

    def test_equipped_stats_and_hp(self):
        set_race_and_class(
            123, "tiefling", "wizard", self.db
        )

        grant_character(123, "arza_zenta", self.db)

        self.assertEqual(
            get_player(123, self.db).hp_max,
            7,
        )

        equip_character(123, "aoe", "arza_zenta", self.db)

        player = get_player(123, self.db)

        self.assertEqual(player.effective_stats["intelligence"], 5)
        self.assertEqual(player.effective_stats["charisma"], 6)
        self.assertEqual(player.effective_stats["constitution"], 2)
        self.assertEqual(player.hp_max, 8)
        self.assertEqual(
            player.party_passives,
            ["mischief", "fire_projectile"],
        )

    def test_unequip_keeps_collection(self):
        grant_character(123, "arza_zenta", self.db)
        equip_character(123, "aoe", "arza_zenta", self.db)

        self.assertTrue(unequip_slot(123, "aoe", self.db))

        self.assertIsNone(
            get_party_slots(123, self.db)["aoe"]
        )
        self.assertEqual(
            get_owned_characters(123, self.db)[0]["character_id"],
            "arza_zenta",
        )
        self.assertEqual(
            get_player(123, self.db).party_passives,
            [],
        )

    def test_replacing_character_in_slot(self):
        catalog = load_character_index()
        catalog["second_aoe"] = {
            **catalog["arza_zenta"],
            "name": "Второй персонаж",
        }

        with patch(
            "src.characters.storage_chars.load_character_index",
            return_value=catalog,
        ):
            grant_character(123, "arza_zenta", self.db)
            grant_character(123, "second_aoe", self.db)

            equip_character(123, "aoe", "arza_zenta", self.db)
            equip_character(123, "aoe", "second_aoe", self.db)

        owned = get_owned_characters(123, self.db)
        equipped = [
            item for item in owned
            if item["slot"] == "aoe"
        ]

        self.assertEqual(len(equipped), 1)
        self.assertEqual(
            equipped[0]["character_id"],
            "second_aoe",
        )

    def test_delete_player_removes_collection(self):
        grant_character(123, "arza_zenta", self.db)
        equip_character(123, "aoe", "arza_zenta", self.db)

        delete_player(123, self.db)

        self.assertEqual(
            get_owned_characters(123, self.db),
            [],
        )


class PartyMenuTests(unittest.IsolatedAsyncioTestCase):

    async def test_party_menu_displays_equipped_character(self):
        user = SimpleNamespace(id=123)

        callback = SimpleNamespace(
            data="mini:profile:party",
            from_user=user,
            message=SimpleNamespace(
                chat=SimpleNamespace(
                    id=-1001,
                    type="supergroup",
                ),
                message_id=99,
                ephemeral_message_id=45,
                receiver_user=user,
            ),
            answer=AsyncMock(),
        )

        bot = SimpleNamespace(
            edit_ephemeral_message_text=AsyncMock(),
        )

        player = SimpleNamespace(
            id=123,
            race="tiefling",
            class_name="wizard",
        )

        slots = {
            "tank": None,
            "dd": None,
            "heal": None,
            "buff": None,
            "aoe": "arza_zenta",
        }

        with patch(
            "src.main.party.get_player",
            return_value=player,
        ):
            with patch(
                "src.main.party.get_party_slots",
                return_value=slots,
            ):
                with patch(
                    "src.main.creation.load_menu_image",
                    return_value=None,
                ):
                    await party_callback(callback, bot)

        text = (
            bot.edit_ephemeral_message_text
            .await_args.kwargs["text"]
        )

        self.assertIn("[АОЕ] - Арза Зента", text)
        self.assertIn("[ДД] - пусто", text)
        callback.answer.assert_awaited_once()

"""Тесты коллекции и экипировки персонажей."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.characters.catalog import load_character_index
from src.characters.storage_chars import (
    equip_character,
    get_owned_characters,
    get_party_slots,
    grant_character,
    unequip_slot,
)
from src.main.party import party_callback
from src.mainplayer.storage import (
    create_player,
    delete_player,
    get_player,
    init_db,
    set_race_and_class,
)


class PartyTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "test.db"

        init_db(self.db)
        init_creation_db(self.db)
        create_player(123, "Герой", self.db)

    def tearDown(self):
        self.temp.cleanup()

    def test_grant_and_equip(self):
        self.assertTrue(
            grant_character(123, "arza_zenta", self.db)
        )
        self.assertFalse(
            grant_character(123, "arza_zenta", self.db)
        )

        self.assertTrue(
            equip_character(123, "aoe", "arza_zenta", self.db)
        )

        self.assertEqual(
            get_party_slots(123, self.db)["aoe"],
            "arza_zenta",
        )

        self.assertFalse(
            equip_character(123, "aoe", "arza_zenta", self.db)
        )

    def test_wrong_slot_and_missing_ownership(self):
        with self.assertRaises(ValueError):
            equip_character(123, "aoe", "arza_zenta", self.db)

        grant_character(123, "arza_zenta", self.db)

        with self.assertRaises(ValueError):
            equip_character(123, "tank", "arza_zenta", self.db)

        self.assertIsNone(get_party_slots(123, self.db)["tank"])

    def test_equipped_stats_and_hp(self):
        set_race_and_class(
            123, "tiefling", "wizard", self.db
        )

        grant_character(123, "arza_zenta", self.db)

        self.assertEqual(
            get_player(123, self.db).hp_max,
            7,
        )

        equip_character(123, "aoe", "arza_zenta", self.db)

        player = get_player(123, self.db)

        self.assertEqual(player.effective_stats["intelligence"], 5)
        self.assertEqual(player.effective_stats["charisma"], 6)
        self.assertEqual(player.effective_stats["constitution"], 2)
        self.assertEqual(player.hp_max, 8)
        self.assertEqual(
            player.party_passives,
            ["mischief", "fire_projectile"],
        )

    def test_unequip_keeps_collection(self):
        grant_character(123, "arza_zenta", self.db)
        equip_character(123, "aoe", "arza_zenta", self.db)

        self.assertTrue(unequip_slot(123, "aoe", self.db))

        self.assertIsNone(
            get_party_slots(123, self.db)["aoe"]
        )
        self.assertEqual(
            get_owned_characters(123, self.db)[0]["character_id"],
            "arza_zenta",
        )
        self.assertEqual(
            get_player(123, self.db).party_passives,
            [],
        )

    def test_replacing_character_in_slot(self):
        catalog = load_character_index()
        catalog["second_aoe"] = {
            **catalog["arza_zenta"],
            "name": "Второй персонаж",
        }

        with patch(
            "src.characters.storage_chars.load_character_index",
            return_value=catalog,
        ):
            grant_character(123, "arza_zenta", self.db)
            grant_character(123, "second_aoe", self.db)

            equip_character(123, "aoe", "arza_zenta", self.db)
            equip_character(123, "aoe", "second_aoe", self.db)

        owned = get_owned_characters(123, self.db)
        equipped = [
            item for item in owned
            if item["slot"] == "aoe"
        ]

        self.assertEqual(len(equipped), 1)
        self.assertEqual(
            equipped[0]["character_id"],
            "second_aoe",
        )

    def test_delete_player_removes_collection(self):
        grant_character(123, "arza_zenta", self.db)
        equip_character(123, "aoe", "arza_zenta", self.db)

        delete_player(123, self.db)

        self.assertEqual(
            get_owned_characters(123, self.db),
            [],
        )


class PartyMenuTests(unittest.IsolatedAsyncioTestCase):

    async def test_party_menu_displays_equipped_character(self):
        user = SimpleNamespace(id=123)

        callback = SimpleNamespace(
            data="mini:profile:party",
            from_user=user,
            message=SimpleNamespace(
                chat=SimpleNamespace(
                    id=-1001,
                    type="supergroup",
                ),
                message_id=99,
                ephemeral_message_id=45,
                receiver_user=user,
            ),
            answer=AsyncMock(),
        )

        bot = SimpleNamespace(
            edit_ephemeral_message_text=AsyncMock(),
        )

        player = SimpleNamespace(
            id=123,
            race="tiefling",
            class_name="wizard",
        )

        slots = {
            "tank": None,
            "dd": None,
            "heal": None,
            "buff": None,
            "aoe": "arza_zenta",
        }

        with patch(
            "src.main.party.get_player",
            return_value=player,
        ):
            with patch(
                "src.main.party.get_party_slots",
                return_value=slots,
            ):
                with patch(
                    "src.main.creation.load_menu_image",
                    return_value=None,
                ):
                    await party_callback(callback, bot)

        text = (
            bot.edit_ephemeral_message_text
            .await_args.kwargs["text"]
        )

        self.assertIn("[АОЕ] - Арза Зента", text)
        self.assertIn("[ДД] - пусто", text)
        callback.answer.assert_awaited_once()
