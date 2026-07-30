# handlers_user.py
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import CommandStart

import database as db
from config import ADMIN_ID

router = Router()


# ---------- ASOSIY MENYU ----------
def main_menu_kb() -> InlineKeyboardMarkup:
    channel_url = db.get_setting("channel_url")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Xizmatlar", callback_data="menu:services")],
        [InlineKeyboardButton(text="👨‍💻 Admin bilan bog'lanish", callback_data="menu:contact")],
        [InlineKeyboardButton(text="📢 Bizning kanal", url=channel_url)],
    ])
    return kb


WELCOME_TEXT = (
    "👋 Assalomu alaykum!\n\n"
    " @khasanv botiga xush kelibsiz. Bu yerda siz Telegram Premium va boshqa "
    "xizmatlarimizni buyurtma qilishingiz mumkin.\n\n"
    "Quyidagi menyudan kerakli bo'limni tanlang 👇"
)


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())


@router.callback_query(F.data == "menu:main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.edit_text(WELCOME_TEXT, reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "menu:contact")
async def contact_admin(callback: CallbackQuery):
    admin_username = db.get_setting("admin_username")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Admin bilan aloqa", url=f"https://t.me/{admin_username.lstrip('@')}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="menu:main")],
    ])
    await callback.message.edit_text(
        f"Admin bilan bog'lanish uchun: {admin_username}",
        reply_markup=kb
    )
    await callback.answer()


# ---------- XIZMATLAR (KATEGORIYALAR) ----------
@router.callback_query(F.data == "menu:services")
async def show_categories(callback: CallbackQuery):
    categories = db.get_categories()
    if not categories:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="menu:main")]
        ])
        await callback.message.edit_text(
            "Hozircha xizmatlar qo'shilmagan. Tez orada qo'shiladi.",
            reply_markup=kb
        )
        await callback.answer()
        return

    buttons = [
        [InlineKeyboardButton(text=cat["name"], callback_data=f"cat:{cat['id']}")]
        for cat in categories
    ]
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="menu:main")])

    await callback.message.edit_text(
        "🛍 Kerakli xizmat turini tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


# ---------- KATEGORIYA ICHIDAGI XIZMATLAR ----------
@router.callback_query(F.data.startswith("cat:"))
async def show_items(callback: CallbackQuery):
    category_id = int(callback.data.split(":")[1])
    category = db.get_category(category_id)
    items = db.get_items_by_category(category_id)

    if not items:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="menu:services")]
        ])
        await callback.message.edit_text(
            f"«{category['name']}» bo'limida hozircha xizmatlar yo'q.",
            reply_markup=kb
        )
        await callback.answer()
        return

    buttons = [
        [InlineKeyboardButton(
            text=f"{item['name']} — {item['price']:,} so'm".replace(",", " "),
            callback_data=f"item:{item['id']}"
        )]
        for item in items
    ]
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="menu:services")])

    await callback.message.edit_text(
        f"📂 {category['name']}:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


# ---------- BITTA XIZMAT HAQIDA MA'LUMOT ----------
@router.callback_query(F.data.startswith("item:"))
async def show_item(callback: CallbackQuery):
    item_id = int(callback.data.split(":")[1])
    item = db.get_item(item_id)

    text = f"📦 {item['name']}\n\n💵 Narxi: {item['price']:,} so'm".replace(",", " ")
    if item["info"]:
        text += f"\n\nℹ️ {item['info']}"
    text += "\n\nAgar olmoqchi bo'lsangiz, admin bilan bog'lab beraman."

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Buyurtma berish", callback_data=f"order:{item['id']}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"cat:{item['category_id']}")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ---------- BUYURTMA BERISH (ADMINGA XABAR) ----------
@router.callback_query(F.data.startswith("order:"))
async def make_order(callback: CallbackQuery, bot: Bot):
    item_id = int(callback.data.split(":")[1])
    item = db.get_item(item_id)
    user = callback.from_user

    username_part = f"@{user.username}" if user.username else "username yo'q"
    admin_text = (
        "🆕 Yangi buyurtma shep!\n\n"
        f"👤 Foydalanuvchi: {user.full_name} ({username_part})\n"
        f"🆔 ID: {user.id}\n\n"
        f"📦 Xizmat: {item['name']}\n"
        f"💵 Narxi: {item['price']:,} so'm".replace(",", " ")
    )

    await bot.send_message(ADMIN_ID, admin_text)

    await callback.answer(
        "✅ Buyurtmangiz qabul qilindi! Tez orada admin siz bilan bog'lanadi.",
        show_alert=True
    )
