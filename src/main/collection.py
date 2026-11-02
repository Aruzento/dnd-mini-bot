
"""Просмотр коллекционных персонажей."""

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from src.characters.catalog import (
    load_character_index,
    load_characters,
    load_hero_passives,
)
from src.characters.storage_chars import (
    SLOT_LABELS,
    get_owned_characters,
)
from src.mainplayer.storage import get_player

from .creation import (
    is_personal_callback,
    next_menu,
    show_callback_menu,
)
from .menus import load_menu


router = Router(name="mini_collection")

PAGE_SIZE = 6

RARITY_NAMES = {
    "common": "Обычные",
    "rare": "Редкие",
    "legendary": "Легендарные",
    "mythic": "Мифические",
}

STAT_SHORT = {
    "strength": "С",
    "dexterity": "Л",
    "constitution": "Т",
    "intelligence": "И",
    "wisdom": "М",
    "charisma": "Х",
}

OBTAIN_NAMES = {
    "gacha": "Гача",
    "alchemy": "Алхимия",
}


def _owned_ids(player_id: int) -> set[str]:
    """ID персонажей, принадлежащих игроку."""

    return {
        item["character_id"]
        for item in get_owned_characters(player_id)
    }


def _stats_text(stats: dict) -> str:
    """Краткая запись характеристик: Т1|И3|М2|Х3."""

    parts = [
        f"{short}{stats[ability]}"
        for ability, short in STAT_SHORT.items()
        if stats.get(ability, 0) != 0
    ]

    return "|".join(parts) if parts else "—"


def _overview_content(player_id: int):
    """Выбор редкости и общий прогресс коллекции."""

    catalog = load_character_index()
    owned = _owned_ids(player_id)

    # Считаем только актуальные ID игровых каталогов.
    collected = len(owned.intersection(catalog))

    return load_menu(
        "collection",
        context={
            "owned": collected,
            "total": len(catalog),
        },
    )


def _list_content(
    player_id: int,
    rarity: str,
    page: int,
):
    """Список персонажей редкости: 6 на страницу."""

    if rarity not in RARITY_NAMES:
        raise ValueError("Неизвестная редкость")

    if type(page) is not int or page < 1:
        raise ValueError("Некорректная страница")

    catalog = load_characters(rarity)
    owned = _owned_ids(player_id)

    characters = sorted(
        catalog.items(),
        key=lambda item: (
            item[1]["name"].casefold(),
            item[0],
        ),
    )

    total_pages = max(
        1,
        (len(characters) + PAGE_SIZE - 1) // PAGE_SIZE,
    )

    # Каталог может увеличиться или уменьшиться между запросами.
    page = min(page, total_pages)

    start = (page - 1) * PAGE_SIZE
    visible = characters[start:start + PAGE_SIZE]

    lines = []
    buttons = []

    for number, (character_id, character) in enumerate(
        visible,
        start=start + 1,
    ):
        owned_mark = (
            "✓" if character_id in owned else "🔒"
        )

        slot_name = SLOT_LABELS.get(
            character["type"],
            character["type"].upper(),
        )

        lines.append(
            f"{number}. {owned_mark} {character['name']}"
            f" - {slot_name} - "
            f"{_stats_text(character['stats'])}"
        )

        buttons.append({
            "text": f"{owned_mark} {character['name']}",
            "callback_data": (
                f"mini:collection:detail:"
                f"{rarity}:{page}:{character_id}"
            ),
        })

    return load_menu(
        "collection_list",
        context={
            "rarity": rarity,
            "rarity_name": RARITY_NAMES[rarity],
            "characters_text": (
                "\n".join(lines)
                if lines else
                "Персонажей этой редкости пока нет."
            ),
            "page": page,
            "total_pages": total_pages,
            "prev_page": max(1, page - 1),
            "next_page": min(total_pages, page + 1),
            "has_prev": page > 1,
            "has_next": page < total_pages,
        },
        dynamic_buttons={
            "characters": buttons,
        },
    )


def _detail_content(
    player_id: int,
    rarity: str,
    page: int,
    character_id: str,
):
    """Карточка выбранного персонажа."""

    if rarity not in RARITY_NAMES:
        raise ValueError("Неизвестная редкость")

    character = load_characters(rarity).get(character_id)

    if character is None:
        raise ValueError("Персонаж не найден")

    owned = _owned_ids(player_id)
    passive_catalog = load_hero_passives()

    passive_lines = []

    for passive_id in character["passives"]:
        passive = passive_catalog[passive_id]

        passive_lines.append(
            f"• {passive['name']}\n"
            f"  {passive['description']}"
        )

    if not passive_lines:
        passive_lines.append("Нет")

    village = character.get("village") or {}
    village_bonus = village.get("productivity_bonus")

    village_text = (
        f"+{village_bonus:g}"
        if village_bonus is not None
        else "Нет бонуса"
    )

    obtain = [
        OBTAIN_NAMES.get(source, source)
        for source in character["obtain"]
    ]

    return load_menu(
        "collection_detail",
        context={
            "name": character["name"],
            "rarity_name": RARITY_NAMES[rarity],
            "slot_name": SLOT_LABELS.get(
                character["type"],
                character["type"].upper(),
            ),
            "status": (
                "Получен"
                if character_id in owned
                else "Не получен"
            ),
            "stats": _stats_text(character["stats"]),
            "passives": "\n".join(passive_lines),
            "village": village_text,
            "obtain": ", ".join(obtain) if obtain else "—",
            "rarity": rarity,
            "page": page,
        },
    )


@router.callback_query(
    (F.data == "mini:profile:collection")
    | F.data.startswith("mini:collection:")
)
async def collection_callback(
    callback: CallbackQuery,
    bot: Bot,
):
    """Открывает коллекцию, страницы и карточки персонажей."""

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
            callback,
            bot,
            current_menu,
            player=player,
        )
        return

    action = callback.data or ""

    if action == "mini:profile:collection":
        content = _overview_content(player_id)

    elif action.startswith("mini:collection:list:"):
        parts = action.split(":")

        if len(parts) != 5:
            await callback.answer(
                "Неверная команда", show_alert=True
            )
            return

        rarity = parts[3]

        try:
            page = int(parts[4])
            content = _list_content(
                player_id, rarity, page
            )
        except (ValueError, KeyError):
            await callback.answer(
                "Некорректная страница или редкость",
                show_alert=True,
            )
            return

    elif action.startswith("mini:collection:detail:"):
        parts = action.split(":")

        if len(parts) != 6:
            await callback.answer(
                "Неверная команда", show_alert=True
            )
            return

        rarity = parts[3]
        character_id = parts[5]

        try:
            page = int(parts[4])

            if page < 1:
                raise ValueError("Некорректная страница")

            content = _detail_content(
                player_id,
                rarity,
                page,
                character_id,
            )
        except (ValueError, KeyError):
            await callback.answer(
                "Персонаж не найден",
                show_alert=True,
            )
            return

    else:
        await callback.answer(
            "Неизвестное действие",
            show_alert=True,
        )
        return

    await show_callback_menu(
        callback,
        bot,
        "collection",
        player=player,
        menu_content=content,
    )
