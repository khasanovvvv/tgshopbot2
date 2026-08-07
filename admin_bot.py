# admin_bot.py
# Faqat siz (admin) uchun alohida bot. Pastda doimiy tugma turadi,
# uni bosganda esa asosiy admin panel (inline tugmalar) ochiladi.
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart

import database as db
from config import ADMIN_ID
from handlers_admin import admin_menu_kb, is_admin

router = Router()

MENU_BUTTON_TEXT = "🛠 Admin panelni ochish"


def admin_reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=MENU_BUTTON_TEXT)]],
        resize_keyboard=True
    )


@router.message(CommandStart())
async def admin_cmd_start(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Bu bot faqat admin uchun.")
        return
    await message.answer(
        "👋 Xush kelibsiz! Pastdagi tugmani bosib, admin panelni oching.",
        reply_markup=admin_reply_kb()
    )


@router.message(F.text == MENU_BUTTON_TEXT)
async def open_admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("🛠 Admin panel:", reply_markup=admin_menu_kb())
