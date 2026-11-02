
"""Меню отряда и управление слотами."""

from aiogram import Bot, F, Router
from aiogram.types import (
    CallbackQuery,
)

from src.characters.catalog import (
    load_character_index,
    load_hero_passives,
)
from src.characters.storage_chars import (
    SLOT_LABELS,
    equip_character,
    get_owned_characters,
    get_party_slots,
    unequip_slot,
)
from src.mainplayer.storage import get_player

from .creation import (
    is_personal_callback,
    next_menu,
    show_callback_menu,
)
from .menus import load_menu


router = Router(name="mini_party")

STAT_LABELS = {
    "strength": "Сила",
    "dexterity": "Ловкость",
    "constitution": "Телосложение",
    "intelligence": "Интеллект",
    "wisdom": "Мудрость",
    "charisma": "Харизма",
}


def _party_content(player_id):
    """Основной экран отряда."""

    slots = get_party_slots(player_id)
    catalog = load_character_index()

    lines = []

    for slot, label in SLOT_LABELS.items():
        character_id = slots[slot]

        name = (
            catalog[character_id]["name"]
            if character_id is not None
            else "пусто"
        )

        lines.append(f"[{label}] - {name}")

    return load_menu(
        "party",
        context={"slots": "\n".join(lines)},
    )


def _change_content():
    """Экран выбора слота."""

    return load_menu("party_change")


def _slot_content(player_id, slot):
    """Выбор персонажа из коллекции для слота."""

    catalog = load_character_index()
    owned = get_owned_characters(player_id)
    current = get_party_slots(player_id)[slot]

    available = []

    for item in owned:
        character_id = item["character_id"]
        character = catalog[character_id]

        if character["type"] != slot:
            continue

        name = character["name"]

        if character_id == current:
            name = f"✓ {name}"

        available.append({
            "text": name,
            "callback_data": (
                f"mini:party:equip:{slot}:{character_id}"
            ),
        })

    prompt = (
        "Выбери персонажа:"
        if available
        else "Подходящих персонажей в коллекции пока нет."
    )

    return load_menu(
        "party_slot",
        context={
            "slot": slot,
            "slot_name": SLOT_LABELS[slot],
            "prompt": prompt,
            "occupied": current is not None,
        },
        dynamic_buttons={
            "characters": available,
        },
    )




def _effects_content(player):
    """Отображает бонусы экипированного отряда."""

    stat_lines = []

    for ability, bonus in player.party_stats.items():
        if bonus:
            stat_lines.append(
                f"{STAT_LABELS[ability]}: +{bonus}"
            )

    if not stat_lines:
        stat_lines.append("Нет бонусов")

    passive_lines = []

    if player.party_passives:
        passive_catalog = load_hero_passives()

        for passive_id in player.party_passives:
            passive = passive_catalog[passive_id]

            passive_lines.append(
                f"• {passive['name']}: "
                f"{passive['description']}"
            )

    if not passive_lines:
        passive_lines.append("Нет пассивок")

    return load_menu(
        "party_effects",
        context={
            "stats": "\n".join(stat_lines),
            "passives": "\n".join(passive_lines),
        },
    )


@router.callback_query(
    (F.data == "mini:profile:party")
    | F.data.startswith("mini:party:")
)
async def party_callback(callback: CallbackQuery, bot: Bot):
    """Навигация и смена экипированных персонажей."""

    if not is_personal_callback(callback):
        await callback.answer(
            "Это не твоё меню",
            show_alert=True,
        )
        return

    player_id = callback.from_user.id
    player = get_player(player_id)
    current_menu = next_menu(player)

    if current_menu != "main":
        await show_callback_menu(
            callback, bot, current_menu, player=player
        )
        return

    action = callback.data

    if action == "mini:profile:party":
        content = _party_content(player_id)

    elif action == "mini:party:change":
        content = _change_content()

    elif action == "mini:party:effects":
        content = _effects_content(player)

    elif action.startswith("mini:party:slot:"):
        slot = action.removeprefix("mini:party:slot:")

        if slot not in SLOT_LABELS:
            await callback.answer("Неизвестный слот", show_alert=True)
            return

        content = _slot_content(player_id, slot)

    elif action.startswith("mini:party:equip:"):
        parts = action.split(":")

        if len(parts) != 5:
            await callback.answer("Неверная команда", show_alert=True)
            return

        _, _, _, slot, character_id = parts

        try:
            equip_character(player_id, slot, character_id)
        except ValueError as error:
            await callback.answer(str(error), show_alert=True)
            return

        content = _party_content(player_id)

    elif action.startswith("mini:party:remove:"):
        slot = action.removeprefix("mini:party:remove:")

        try:
            unequip_slot(player_id, slot)
        except ValueError as error:
            await callback.answer(str(error), show_alert=True)
            return

        content = _party_content(player_id)

    else:
        await callback.answer("Неизвестное действие", show_alert=True)
        return

    await show_callback_menu(
        callback,
        bot,
        "party",
        player=player,
        menu_content=content,
    )
