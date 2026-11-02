
"""Административные команды тестового Mini 2.0."""

import logging
import os
import re
import sqlite3
import asyncio
from dataclasses import dataclass, field

from aiogram import F
from aiogram.filters.command import CommandException
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


async def is_admin_message(message: Message, bot: Bot) -> bool:
    """Проверяет ID администратора и его права в группе."""

    if message.from_user is None:
        return False

    if not is_allowed_admin(message.from_user.id):
        return False

    if message.chat.type not in GROUP_TYPES | {"private"}:
        return False

    if message.chat.type in GROUP_TYPES:
        try:
            member = await bot.get_chat_member(
                message.chat.id,
                message.from_user.id,
            )
        except TelegramAPIError:
            logger.exception(
                "Не удалось проверить администратора"
            )
            return False

        if member.status not in ADMIN_STATUSES:
            return False

    return True


@router.message(Command("admdel"))
async def admin_delete_character(
    message: Message,
    bot: Bot,
    command: CommandObject,
):
    """Полностью удаляет персонажа выбранного пользователя."""

    if not await is_admin_message(message, bot):
        return

    is_group = message.chat.type in GROUP_TYPES

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


# Интервал без новых сообщений, после которого считаем
# альбом полученным.
ALBUM_SETTLE_SECONDS = 1.0

IMAGE_COMMAND = Command("admimage")


@dataclass
class PendingImageAlbum:
    images: dict[int, Message] = field(default_factory=dict)
    command_found: bool = False
    last_message_at: float = 0.0


# Временное состояние только для получаемых альбомов.
_pending_image_albums: dict[
    tuple[int, int, str], PendingImageAlbum
] = {}


async def _has_admimage_command(
    message: Message,
    bot: Bot,
) -> bool:
    """Проверяет команду в подписи, включая @имя_бота."""

    if not message.caption:
        return False

    try:
        await IMAGE_COMMAND.parse_command(
            text=message.caption,
            bot=bot,
        )
    except CommandException:
        return False

    return True


def _photo_file_id(message: Message) -> str:
    """Возвращает file_id наибольшего размера фотографии."""

    largest = max(
        message.photo,
        key=lambda photo: (
            photo.width * photo.height,
            photo.file_size or 0,
        ),
    )

    return largest.file_id


def _image_ids_text(messages: list[Message]) -> str:
    """Формирует ответ, сохраняя порядок фотографий."""

    ordered = sorted(
        messages,
        key=lambda message: message.message_id,
    )

    ids = [_photo_file_id(message) for message in ordered]

    if len(ids) == 1:
        return f"file_id:\n{ids[0]}"

    lines = [
        f"{index}. {file_id}"
        for index, file_id in enumerate(ids, start=1)
    ]

    return "file_id изображений:\n" + "\n".join(lines)


@router.message(F.photo)
async def admin_image_photo(message: Message, bot: Bot):
    """Получает ID одиночной фотографии или всего альбома."""

    if message.from_user is None:
        return

    if not is_allowed_admin(message.from_user.id):
        return

    if message.chat.type not in GROUP_TYPES | {"private"}:
        return

    requested = await _has_admimage_command(message, bot)

    # Одна фотография.
    if message.media_group_id is None:
        if not requested:
            return

        if not await is_admin_message(message, bot):
            return

        await admin_reply(
            message,
            bot,
            _image_ids_text([message]),
        )
        return

    # Фотографии альбома приходят отдельными сообщениями.
    key = (
        message.chat.id,
        message.from_user.id,
        message.media_group_id,
    )

    album = _pending_image_albums.get(key)
    first_received = album is None

    if first_received:
        album = PendingImageAlbum()
        _pending_image_albums[key] = album

    album.images[message.message_id] = message
    album.command_found |= requested

    loop = asyncio.get_running_loop()
    album.last_message_at = loop.time()

    # Только первый обработчик ожидает завершения альбома.
    if not first_received:
        return

    try:
        while True:
            await asyncio.sleep(ALBUM_SETTLE_SECONDS)

            elapsed = loop.time() - album.last_message_at

            if elapsed >= ALBUM_SETTLE_SECONDS:
                break

        # Без команды /admimage обычные альбомы игнорируем.
        if not album.command_found:
            return

        if not await is_admin_message(message, bot):
            return

        await admin_reply(
            message,
            bot,
            _image_ids_text(list(album.images.values())),
        )

    finally:
        # Не оставляем обработанные альбомы в памяти.
        if _pending_image_albums.get(key) is album:
            del _pending_image_albums[key]


@router.message(Command("admimage"))
async def admin_image_usage(message: Message, bot: Bot):
    """Подсказка, если команда отправлена без фотографии."""

    if not await is_admin_message(message, bot):
        return

    await admin_reply(
        message,
        bot,
        "Пришли фотографию или альбом с подписью "
        "/admimage.",
    )
