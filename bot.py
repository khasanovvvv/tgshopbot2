# bot.py
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
import database as db
import handlers_user
import handlers_admin


async def main():
    logging.basicConfig(level=logging.INFO)

    db.init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # admin handlerlar user handlerlardan OLDIN ro'yxatdan o'tishi kerak,
    # aks holda callback_data mos kelib qolishi mumkin
    dp.include_router(handlers_admin.router)
    dp.include_router(handlers_user.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
