
"""Меню профиля игрока."""

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from src.mainplayer.storage import get_player
from .creation import (
    is_personal_callback,
    next_menu,
    show_callback_menu,
)

router = Router(name="mini_profile")



PROFILE_MENUS = {
    "mini:profile": "profile",
    "mini:profile:party": "party",
    "mini:profile:stats": "stats",
    "mini:profile:collection": "collection",
    "mini:profile:gallery": "gallery",
}


@router.callback_query(F.data.in_(PROFILE_MENUS))
async def profile_callback(callback: CallbackQuery, bot: Bot):
    """Навигация по разделам профиля."""

    if not is_personal_callback(callback):
        await callback.answer(
            "Это не твоё меню",
            show_alert=True,
        )
        return

    player = get_player(callback.from_user.id)
    current_menu = next_menu(player)

    target = (
        PROFILE_MENUS[callback.data]
        if current_menu == "main"
        else current_menu
    )

    await show_callback_menu(
        callback,
        bot,
        target,
        player=player,
    )
