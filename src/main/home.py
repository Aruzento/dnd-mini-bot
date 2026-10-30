"""Private menus in group chats, public pinned launcher, and commands."""

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    EphemeralMessageParameters,
    Message,
)

from src.mainplayer.storage import (
    get_player,
    remember_player_username,
)
from .menus import load_menu
from .creation import (
    is_personal_callback,
    next_menu,
    send_menu,
    show_callback_menu,
)

router = Router()
logger = logging.getLogger(__name__)
GROUP_TYPES = {"group", "supergroup"}
ADMIN_STATUSES = {"administrator", "creator"}


def player_menu(user_id: int) -> str:
    return next_menu(get_player(user_id))

"""@router.message(F.photo)
async def temporary_photo_id(message: Message):
    if message.chat.type == "private":
        await message.answer(message.photo[-1].file_id)"""

@router.callback_query(F.data == "mini:main")
async def main_callback(callback: CallbackQuery, bot: Bot):
    """Возврат в главное меню героя."""
    if not is_personal_callback(callback):
        await callback.answer(
            "Это не твоё меню",
            show_alert=True,
        )
        return

    player = get_player(callback.from_user.id)

    await show_callback_menu(
        callback,
        bot,
        next_menu(player),
        player=player,
    )


@router.message(CommandStart())
async def start_command(message: Message) -> None:
    await message.answer("D&D Mini 2.0 запущен!")


@router.message(Command("minicreate"))
async def create_launcher(message: Message, bot: Bot) -> None:
    """Pin one public launcher. Only a chat administrator may run this."""
    if message.chat.type not in GROUP_TYPES or message.from_user is None:
        return

    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status not in ADMIN_STATUSES:
        return

    text, keyboard = load_menu("launcher")
    # Launcher is intentionally public; only the resulting personal menus are private.
    sent = await bot.send_message(
        chat_id=message.chat.id,
        message_thread_id=message.message_thread_id,
        text=text,
        reply_markup=keyboard,
    )
    try:
        await bot.pin_chat_message(
            chat_id=message.chat.id,
            message_id=sent.message_id,
            disable_notification=True,
        )
    except TelegramAPIError:
        logger.exception("Could not pin Mini launcher in chat %s", message.chat.id)
        # Never send a public error message; the launcher itself remains in the chat.
        try:
            await bot.send_message(
                chat_id=message.chat.id,
                text="Лаунчер опубликован, но закрепить его не удалось. Проверь права бота.",
                ephemeral_message_parameters=EphemeralMessageParameters(
                    receiver_user_id=message.from_user.id
                ),
            )
        except TelegramAPIError:
            logger.exception("Could not notify admin about launcher pin failure")



@router.message(Command("mini"))
async def mini_command(message: Message, bot: Bot) -> None:
    if message.from_user is None:
        return

    player = get_player(message.from_user.id)
    if hasattr(message.from_user, "username"):
        remember_player_username(
            message.from_user.id,
            message.from_user.username,
        )
    menu_name = next_menu(player)

    if message.chat.type == "private":
        await send_menu(
            bot,
            menu_name,
            message.chat.id,
            player=player,
        )
        return

    if message.chat.type not in GROUP_TYPES:
        return

    try:
        await send_menu(
            bot,
            menu_name,
            message.chat.id,
            player=player,
            message_thread_id=message.message_thread_id,
            ephemeral_message_parameters=EphemeralMessageParameters(
                receiver_user_id=message.from_user.id,
            ),
        )
    except TelegramAPIError:
        logger.exception(
            "Failed to show ephemeral /mini for user %s",
            message.from_user.id,
        )



@router.callback_query(F.data == "mini:play")
async def play_callback(callback: CallbackQuery, bot: Bot) -> None:
    message = callback.message

    if message is None:
        await callback.answer()
        return

    # Запрещаем открывать чужое персональное меню
    receiver = getattr(message, "receiver_user", None)
    if receiver is not None and receiver.id != callback.from_user.id:
        await callback.answer(
            "Это меню другого игрока",
            show_alert=True
        )
        return

    # Получаем персонажа и определяем нужное меню
    player = get_player(callback.from_user.id)
    if hasattr(callback.from_user, "username"):
        remember_player_username(
            callback.from_user.id,
            callback.from_user.username,
        )
    menu_name = next_menu(player)

    old_ephemeral_id = getattr(
        message, "ephemeral_message_id", None
    )

    
    try:
        if message.chat.type == "private":
            await send_menu(
                bot,
                menu_name,
                message.chat.id,
                player=player,
            )

        elif message.chat.type in GROUP_TYPES:
            await send_menu(
                bot,
                menu_name,
                message.chat.id,
                player=player,
                message_thread_id=getattr(
                    message, "message_thread_id", None
                ),
                ephemeral_message_parameters=EphemeralMessageParameters(
                    receiver_user_id=callback.from_user.id,
                    callback_query_id=callback.id,
                    replace_callback_query_message=False,
                ),
            )
        else:
            await callback.answer()
            return

    except TelegramAPIError:
        logger.exception("Failed to open menu for %s", callback.from_user.id)
        await callback.answer(
            "Не удалось открыть меню.",
            show_alert=True,
        )
        return


    except TelegramAPIError:
        logger.exception("Failed to open menu for %s", callback.from_user.id)
        await callback.answer(
            "Не удалось открыть меню.",
            show_alert=True
        )
        return

    await callback.answer()

    # Удаляем старое ЛИЧНОЕ меню только после успешной отправки
    try:
        if old_ephemeral_id is not None:
            await bot.delete_ephemeral_message(
                chat_id=message.chat.id,
                receiver_user_id=callback.from_user.id,
                ephemeral_message_id=old_ephemeral_id,
            )

        elif message.chat.type == "private":
            await bot.delete_message(
                chat_id=message.chat.id,
                message_id=message.message_id,
            )

    except TelegramAPIError:
        # Если удаление не удалось, новое меню продолжит работать
        logger.warning(
            "Could not delete previous personal menu",
            exc_info=True,
        )
