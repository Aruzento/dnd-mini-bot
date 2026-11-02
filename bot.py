"""Minimal entrypoint. Telegram commands and menus live under main/."""

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from src.main.home import router as home_router
from src.main.party import router as party_router
from src.main.profile import router as profile_router
from src.main.locations import router as locations_router
from src.adm.commands import router as admin_router
from src.main.collection import router as collection_router
from src.mainplayer.storage import init_db
from src.main.creation import (
    init_creation_db,
    router as creation_router,
)

load_dotenv("/srv/mini_utl/access_utl/bot.env")
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN не найден")


async def main():
    logging.basicConfig(level=logging.INFO)
    init_db()
    init_creation_db()
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_routers(
        admin_router,
        home_router,
        party_router,
        collection_router,
        profile_router,
        locations_router,
        creation_router,
    )
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
