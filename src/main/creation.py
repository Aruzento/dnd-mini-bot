
"""Создание персонажа: имя, раса и класс."""

import logging
import re
import sqlite3
import time
from contextlib import closing

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.types import (
    CallbackQuery,
    EphemeralMessageParameters,
    Message,
)

from src.mainplayer.storage import (
    DB_PATH,
    create_player,
    get_player,
    set_class,
    remember_player_username,
    set_race,
)
from .menus import load_menu, load_menu_image
from src.mainplayer.catalog import load_character_catalog

router = Router(name="mini_creation")
logger = logging.getLogger(__name__)

GROUP_TYPES = {"group", "supergroup"}


def init_creation_db(db_path=DB_PATH):
    """Таблица для ID меню-подсказок."""
    with closing(sqlite3.connect(db_path, timeout=10)) as conn, conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS creation_prompts (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                ephemeral_id INTEGER,
                message_id INTEGER,
                saved_at INTEGER NOT NULL,
                PRIMARY KEY (chat_id, user_id)
            )
        """)


def save_prompt(message, user_id, db_path=DB_PATH):
    """Запоминает меню, которое нужно удалить после /create."""
    ephemeral_id = getattr(message, "ephemeral_message_id", None)
    message_id = message.message_id if ephemeral_id is None else None

    with closing(sqlite3.connect(db_path, timeout=10)) as conn, conn:
        conn.execute("""
            INSERT INTO creation_prompts
                (chat_id, user_id, ephemeral_id, message_id, saved_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(chat_id, user_id) DO UPDATE SET
                ephemeral_id = excluded.ephemeral_id,
                message_id = excluded.message_id,
                saved_at = excluded.saved_at
        """, (
            message.chat.id,
            user_id,
            ephemeral_id,
            message_id,
            int(time.time()),
        ))


def take_prompt(chat_id, user_id, db_path=DB_PATH):
    """Получает сохранённое меню и удаляет запись о нём."""
    with closing(sqlite3.connect(db_path, timeout=10)) as conn, conn:
        row = conn.execute("""
            SELECT ephemeral_id, message_id, saved_at
            FROM creation_prompts
            WHERE chat_id = ? AND user_id = ?
        """, (chat_id, user_id)).fetchone()

        conn.execute("""
            DELETE FROM creation_prompts
            WHERE chat_id = ? AND user_id = ?
        """, (chat_id, user_id))

    return row


def next_menu(player):
    """Определяет текущий этап регистрации."""
    if player is None:
        return "create"
    if player.race is None:
        return "race"
    if player.class_name is None:
        return "class"
    return "main"


def is_personal_callback(callback):
    """Не допускает действия из чужого или публичного меню."""
    message = callback.message
    if message is None:
        return False

    receiver = getattr(message, "receiver_user", None)
    if receiver is not None and receiver.id != callback.from_user.id:
        return False

    if message.chat.type == "private":
        return True

    return (
        message.chat.type in GROUP_TYPES
        and getattr(message, "ephemeral_message_id", None) is not None
    )


async def send_menu(
    bot,
    menu_name,
    chat_id,
    player=None,
    message_thread_id=None,
    ephemeral_message_parameters=None,
):
    """Отправляет текстовое меню или фото с подписью."""
    text, keyboard = load_menu(menu_name, player=player)
    file_id = load_menu_image(menu_name)

    kwargs = {
        "chat_id": chat_id,
        "reply_markup": keyboard,
    }

    if message_thread_id is not None:
        kwargs["message_thread_id"] = message_thread_id

    if ephemeral_message_parameters is not None:
        kwargs["ephemeral_message_parameters"] = (
            ephemeral_message_parameters
        )

    if file_id:
        if len(text) > 1024:
            raise ValueError("Подпись изображения слишком длинная")

        return await bot.send_photo(
            photo=file_id,
            caption=text,
            **kwargs,
        )

    return await bot.send_message(
        text=text,
        **kwargs,
    )



async def edit_private_menu(callback, bot, menu_name, player=None):
    """Обновляет личное меню с учётом типа сообщения."""
    if not is_personal_callback(callback):
        raise ValueError("Это не личное меню игрока")

    message = callback.message
    text, keyboard = load_menu(menu_name, player=player)

    target_has_photo = bool(load_menu_image(menu_name))
    current_has_photo = bool(getattr(message, "photo", None))

    # При смене типа сообщения отправляем новое личное меню.
    if target_has_photo != current_has_photo:
        params = None

        if message.chat.type in GROUP_TYPES:
            params = EphemeralMessageParameters(
                receiver_user_id=callback.from_user.id,
                callback_query_id=callback.id,
                replace_callback_query_message=False,
            )

        sent = await send_menu(
            bot,
            menu_name,
            message.chat.id,
            player=player,
            message_thread_id=getattr(
                message, "message_thread_id", None
            ),
            ephemeral_message_parameters=params,
        )

        # Новое меню отправлено. Старое теперь можно удалить.
        try:
            if message.chat.type == "private":
                await bot.delete_message(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                )
            else:
                await bot.delete_ephemeral_message(
                    chat_id=message.chat.id,
                    receiver_user_id=callback.from_user.id,
                    ephemeral_message_id=message.ephemeral_message_id,
                )
        except TelegramAPIError:
            logger.warning(
                "Не удалось удалить предыдущее личное меню",
                exc_info=True,
            )

        return sent

    # Если оба меню являются фотографиями, меняем подпись.
    if current_has_photo:
        if len(text) > 1024:
            raise ValueError("Подпись изображения слишком длинная")

        if message.chat.type == "private":
            await bot.edit_message_caption(
                chat_id=message.chat.id,
                message_id=message.message_id,
                caption=text,
                reply_markup=keyboard,
            )
        else:
            await bot.edit_ephemeral_message_caption(
                chat_id=message.chat.id,
                receiver_user_id=callback.from_user.id,
                ephemeral_message_id=message.ephemeral_message_id,
                caption=text,
                reply_markup=keyboard,
            )

    # Обычное текстовое меню редактируем как раньше.
    elif message.chat.type == "private":
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=text,
            reply_markup=keyboard,
        )
    else:
        await bot.edit_ephemeral_message_text(
            chat_id=message.chat.id,
            receiver_user_id=callback.from_user.id,
            ephemeral_message_id=message.ephemeral_message_id,
            text=text,
            reply_markup=keyboard,
        )

    return message


async def show_callback_menu(
    callback, bot, menu_name, remember=False, player=None
):
    """Общий переход для кнопок регистрации."""
    try:
        message = await edit_private_menu(
            callback, bot, menu_name, player=player
        )

        if remember:
            save_prompt(message, callback.from_user.id)

    except (TelegramAPIError, ValueError, sqlite3.Error):
        logger.exception("Не удалось открыть меню %s", menu_name)
        await callback.answer(
            "Не удалось открыть меню. Попробуй /mini.",
            show_alert=True,
        )
        return

    await callback.answer()


async def send_command_menu(message, bot, menu_name, player=None):
    """Показывает меню после команды /create."""
    is_group = message.chat.type in GROUP_TYPES

    params = None

    if is_group:
        params = EphemeralMessageParameters(
            receiver_user_id=message.from_user.id,
        )

    return await send_menu(
        bot,
        menu_name,
        message.chat.id,
        player=player,
        message_thread_id=(
            message.message_thread_id if is_group else None
        ),
        ephemeral_message_parameters=params,
    )


async def delete_command_message(message, bot):
    """Удаляет введённую команду /create."""
    try:
        ephemeral_id = getattr(message, "ephemeral_message_id", None)

        if ephemeral_id is not None:
            await bot.delete_ephemeral_message(
                chat_id=message.chat.id,
                receiver_user_id=message.from_user.id,
                ephemeral_message_id=ephemeral_id,
            )
        else:
            await bot.delete_message(
                chat_id=message.chat.id,
                message_id=message.message_id,
            )

    except TelegramAPIError:
        logger.warning(
            "Не удалось удалить команду /create",
            exc_info=True,
        )


async def delete_old_prompt(message, bot):
    """Удаляет старую подсказку, не затрагивая закреп."""
    saved = take_prompt(
        message.chat.id,
        message.from_user.id,
    )
    if saved is None:
        return

    ephemeral_id, message_id, saved_at = saved

    # Старые ephemeral ID могут перестать быть действительными.
    if time.time() - saved_at > 1800:
        return

    try:
        if ephemeral_id is not None:
            await bot.delete_ephemeral_message(
                chat_id=message.chat.id,
                receiver_user_id=message.from_user.id,
                ephemeral_message_id=ephemeral_id,
            )
        elif message_id is not None:
            await bot.delete_message(
                chat_id=message.chat.id,
                message_id=message_id,
            )

    except TelegramAPIError:
        logger.warning(
            "Не удалось удалить меню-подсказку",
            exc_info=True,
        )


@router.callback_query(F.data == "mini:create")
async def create_button(callback: CallbackQuery, bot: Bot):
    """Кнопка Создать."""
    player = get_player(callback.from_user.id)
    menu_name = "name" if player is None else next_menu(player)

    await show_callback_menu(
        callback,
        bot,
        menu_name,
        remember=(menu_name == "name"),
        player=player,
    )


@router.message(Command("create"))
async def create_command(
    message: Message,
    bot: Bot,
    command: CommandObject,
):
    """Команда /create "Имя"."""
    if message.from_user is None:
        return
    if message.chat.type not in GROUP_TYPES | {"private"}:
        return

    player = get_player(message.from_user.id)

    if player is None:
        raw_name = (command.args or "").strip()

        quote_pairs = {
            '"': '"',
            '«': '»',
            '“': '”',
        }

        if raw_name and raw_name[0] in quote_pairs:
            closing_quote = quote_pairs[raw_name[0]]

            if raw_name.endswith(closing_quote) and len(raw_name) >= 2:
                name = raw_name[1:-1].strip()
            else:
                name = ""
        else:
            name = raw_name

        forbidden = '"«»“”\r\n'

        if (
            not 1 <= len(name) <= 32
            or any(char in name for char in forbidden)
        ):
            name = ""

        if not name:
            await delete_command_message(message, bot)
            try:
                await send_command_menu(message, bot, "name")
            except TelegramAPIError:
                logger.exception("Не удалось показать подсказку имени")
            return

        try:
            player = create_player(message.from_user.id, name)
        except sqlite3.IntegrityError:
            # Защита от двух почти одновременных команд.
            player = get_player(message.from_user.id)

    if player is not None and hasattr(message.from_user, "username"):
        remember_player_username(
            message.from_user.id,
            message.from_user.username,
        )
    menu_name = next_menu(player)

    # Удаляем команду, содержащую имя.
    await delete_command_message(message, bot)

    try:
        await send_command_menu(
            message,
            bot,
            menu_name,
            player=player,
        )
    except TelegramAPIError:
        logger.exception(
            "Не удалось показать меню %s после /create",
            menu_name,
        )
        return

    # Новое меню уже отправлено: теперь удаляем прежнее.
    await delete_old_prompt(message, bot)


@router.callback_query(F.data.startswith("mini:race:"))
async def choose_race(callback: CallbackQuery, bot: Bot):
    """Выбор расы."""
    if not is_personal_callback(callback):
        await callback.answer("Это не твоё меню", show_alert=True)
        return

    code = (callback.data or "").removeprefix("mini:race:")
    if code not in load_character_catalog("races"):
        await callback.answer("Неизвестная раса", show_alert=True)
        return

    player = get_player(callback.from_user.id)
    if player is not None and player.race is None:
        set_race(callback.from_user.id, code)

    player = get_player(callback.from_user.id)
    await show_callback_menu(
        callback,
        bot,
        next_menu(player),
        player=player,
    )


@router.callback_query(F.data.startswith("mini:class:"))
async def choose_class(callback: CallbackQuery, bot: Bot):
    """Выбор класса."""
    if not is_personal_callback(callback):
        await callback.answer("Это не твоё меню", show_alert=True)
        return

    code = (callback.data or "").removeprefix("mini:class:")
    if code not in load_character_catalog("classes"):
        await callback.answer("Неизвестный класс", show_alert=True)
        return

    player = get_player(callback.from_user.id)
    if (
        player is not None
        and player.race is not None
        and player.class_name is None
    ):
        set_class(callback.from_user.id, code)

    player = get_player(callback.from_user.id)
    await show_callback_menu(
        callback,
        bot,
        next_menu(player),
        player=player,
    )
