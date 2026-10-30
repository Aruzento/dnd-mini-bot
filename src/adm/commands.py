
"""Административные команды тестового Mini 2.0."""

import logging
import os
import re
import sqlite3

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.types import EphemeralMessageParameters, Message

from src.mainplayer.storage import (
    delete_player,
    find_player_id_by_username,
)

router = Router(name="mini_admin")
logger = logging.getLogger(__name__)

GROUP_TYPES = {"group", "supergroup"}
ADMIN_STATUSES = {"administrator", "creator"}


def is_allowed_admin(user_id: int) -> bool:
    """Разрешаем команды только указанным Telegram ID."""

    admin_ids = {
        value.strip()
        for value in os.getenv("MINI_ADMIN_IDS", "").split(",")
        if value.strip()
    }

    return str(user_id) in admin_ids


async def admin_reply(message: Message, bot: Bot, text: str):
    """В группе отвечаем лично администратору."""

    if message.chat.type in GROUP_TYPES:
        await bot.send_message(
            chat_id=message.chat.id,
            text=text,
            ephemeral_message_parameters=EphemeralMessageParameters(
                receiver_user_id=message.from_user.id,
            ),
        )
    else:
        await message.answer(text)


@router.message(Command("admdel"))
async def admin_delete_character(
    message: Message,
    bot: Bot,
    command: CommandObject,
):
    """Полностью удаляет персонажа выбранного пользователя."""

    if message.from_user is None:
        return

    if not is_allowed_admin(message.from_user.id):
        return

    if message.chat.type not in GROUP_TYPES | {"private"}:
        return

    is_group = message.chat.type in GROUP_TYPES

    if is_group:
        try:
            member = await bot.get_chat_member(
                message.chat.id,
                message.from_user.id,
            )
        except TelegramAPIError:
            logger.exception("Не удалось проверить администратора")
            return

        if member.status not in ADMIN_STATUSES:
            return

    argument = (command.args or "").strip()

    if re.fullmatch(r"@[A-Za-z0-9_]{5,32}", argument):
        username = argument[1:]

        target_id = find_player_id_by_username(username)

        if target_id is None:
            await admin_reply(
                message,
                bot,
                "Персонаж с таким username не найден. "
                "Попроси игрока открыть /mini или используй Telegram ID.",
            )
            return

        # Проверяем, что сохранённый username всё ещё
        # принадлежит этому Telegram-пользователю.
        if not is_group:
            await admin_reply(
                message,
                bot,
                "По @username удаление доступно в группе. "
                "В личном чате используй числовой Telegram ID.",
            )
            return

        try:
            target_member = await bot.get_chat_member(
                message.chat.id,
                target_id,
            )
        except TelegramAPIError:
            await admin_reply(
                message,
                bot,
                "Не удалось проверить владельца username. "
                "Используй Telegram ID.",
            )
            return

        target_user = getattr(target_member, "user", None)
        actual_username = getattr(target_user, "username", None)

        if (
            actual_username is None
            or actual_username.casefold() != username.casefold()
        ):
            await admin_reply(
                message,
                bot,
                "Username изменился или принадлежит другому "
                "пользователю. Удаление отменено.",
            )
            return

    elif re.fullmatch(r"[1-9][0-9]*", argument):
        target_id = int(argument)

    else:
        await admin_reply(
            message,
            bot,
            "Использование: /admdel @username "
            "или /admdel TELEGRAM_ID",
        )
        return

    try:
        deleted = delete_player(target_id)
    except sqlite3.Error:
        logger.exception("Ошибка удаления персонажа")
        await admin_reply(
            message,
            bot,
            "Ошибка SQLite. Персонаж не удалён.",
        )
        return

    if deleted:
        await admin_reply(
            message,
            bot,
            "Персонаж удалён безвозвратно. "
            "Пользователь может начать создание заново через /mini.",
        )
    else:
        await admin_reply(
            message,
            bot,
            "У пользователя нет персонажа.",
        )
