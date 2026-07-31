# handlers_user.py
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from config import ADMIN_ID

router = Router()


# ---------- FSM (promokod kiritish uchun) ----------
class PromoState(StatesGroup):
    item_id = State()
    waiting_code = State()


# ---------- Premium (maxsus animatsion) emojilar ----------
# Bular faqat XABAR MATNIDA ko'rinadi (Telegram Bot API cheklovi tufayli
# tugma matnida hech qanday bot buni ko'rsata olmaydi). Faqat Telegram
# Premium foydalanuvchilar animatsiyasini ko'radi, boshqalar oddiy emojini
# ko'radi - shuning uchun bu xavfsiz "graceful fallback".
CUSTOM_EMOJI = {
    "wave": "5472235990955334730",       # 👋
    "new": "5382357040008021292",        # 🆕
    "fire": "5424972470023104089",       # 🔥
    "check": "5206607081334906820",      # ✔️
}


def tge(name: str, fallback: str) -> str:
    """Maxsus emoji uchun HTML <tg-emoji> tegini qaytaradi."""
    emoji_id = CUSTOM_EMOJI.get(name)
    if not emoji_id:
        return fallback
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


# ---------- ASOSIY MENYU ----------
def main_menu_kb() -> InlineKeyboardMarkup:
    channel_url = db.get_setting("channel_url")
    e_services = db.get_setting("emoji_services") or "🛍"
    e_contact = db.get_setting("emoji_contact") or "👨‍💻"
    e_channel = db.get_setting("emoji_channel") or "📢"
    e_top = db.get_setting("emoji_top") or "🔥"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{e_services} Xizmatlar", callback_data="menu:services")],
        [InlineKeyboardButton(text=f"{e_top} Top takliflar", callback_data="menu:top")],
        [InlineKeyboardButton(text=f"{e_contact} Admin bilan aloqa", callback_data="menu:contact")],
        [InlineKeyboardButton(text=f"{e_channel} Biz kanali", url=channel_url)],
    ])
    return kb


def back_button(callback_data: str) -> InlineKeyboardButton:
    e_back = db.get_setting("emoji_back") or "🔙"
    return InlineKeyboardButton(text=f"{e_back} Orqaga", callback_data=callback_data)


WELCOME_TEXT = (
    f"Assalomu alaykum! {tge('wave', '👋')}\n\n"
    "✨ Bizning botga xush kelibsiz. Bu yerda siz ⭐ <b>Telegram Premium</b> va boshqa "
    "xizmatlarimizni buyurtma qilishingiz mumkin.\n\n"
    "Quyidagi menyudan kerakli bo'limni tanlang 👇"
)


@router.message(CommandStart())
async def cmd_start(message: Message):
    db.add_user(message.from_user.id)
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())


@router.callback_query(F.data == "menu:main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.edit_text(WELCOME_TEXT, reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "menu:contact")
async def contact_admin(callback: CallbackQuery):
    admin_username = db.get_setting("admin_username")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Admin bilan yozish", url=f"https://t.me/{admin_username.lstrip('@')}")],
        [back_button("menu:main")],
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
    e_services = db.get_setting("emoji_services") or "🛍"

    if not categories:
        kb = InlineKeyboardMarkup(inline_keyboard=[[back_button("menu:main")]])
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
    buttons.append([back_button("menu:main")])

    header = f"{tge('new', '🆕')} {e_services} Kerakli xizmat turini tanlang:"
    await callback.message.edit_text(
        header,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


# ---------- TOP TAKLIFLAR ----------
@router.callback_query(F.data == "menu:top")
async def show_top_items(callback: CallbackQuery):
    items = db.get_top_items()

    if not items:
        kb = InlineKeyboardMarkup(inline_keyboard=[[back_button("menu:main")]])
        await callback.message.edit_text(
            "Hozircha Top takliflar belgilanmagan.",
            reply_markup=kb
        )
        await callback.answer()
        return

    buttons = [
        [InlineKeyboardButton(
            text=f"🔥 {item['name']} — {item['price']:,} so'm".replace(",", " "),
            callback_data=f"item:{item['id']}"
        )]
        for item in items
    ]
    buttons.append([back_button("menu:main")])

    header = f"{tge('fire', '🔥')} <b>Top takliflar</b>:"
    await callback.message.edit_text(
        header,
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
        kb = InlineKeyboardMarkup(inline_keyboard=[[back_button("menu:services")]])
        await callback.message.edit_text(
            f"«{category['name']}» bo'limida hozircha xizmatlar yo'q.",
            reply_markup=kb
        )
        await callback.answer()
        return

    buttons = [
        [InlineKeyboardButton(
            text=("🔥 " if item["is_top"] else "") + f"{item['name']} — {item['price']:,} so'm".replace(",", " "),
            callback_data=f"item:{item['id']}"
        )]
        for item in items
    ]
    buttons.append([back_button("menu:services")])

    await callback.message.edit_text(
        f"📂 {category['name']}:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


# ---------- BITTA XIZMAT HAQIDA MA'LUMOT ----------
@router.callback_query(F.data.startswith("item:"))
async def show_item(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    item_id = int(callback.data.split(":")[1])
    item = db.get_item(item_id)

    top_label = f"{tge('fire', '🔥')} <b>Top taklif!</b>\n\n" if item["is_top"] else ""
    text = f"{top_label}📦 {item['name']}\n\n💵 Narxi: {item['price']:,} so'm".replace(",", " ")
    if item["info"]:
        text += f"\n\nℹ️ {item['info']}"
    text += "\n\nAgar olmoqchi bo'lsangiz, admin bilan bog'lab beraman."

    e_order = db.get_setting("emoji_order") or "✅"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{e_order} Buyurtma berish", callback_data=f"order:{item['id']}")],
        [InlineKeyboardButton(text="🎟 Promokod kiritish", callback_data=f"promo:{item['id']}")],
        [back_button(f"cat:{item['category_id']}")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ---------- PROMOKOD KIRITISH ----------
@router.callback_query(F.data.startswith("promo:"))
async def promo_start(callback: CallbackQuery, state: FSMContext):
    item_id = int(callback.data.split(":")[1])
    await state.update_data(item_id=item_id)
    await state.set_state(PromoState.waiting_code)
    kb = InlineKeyboardMarkup(inline_keyboard=[[back_button(f"item:{item_id}")]])
    await callback.message.edit_text("🎟 Promokodni kiriting:", reply_markup=kb)
    await callback.answer()


@router.message(PromoState.waiting_code)
async def promo_check(message: Message, state: FSMContext):
    data = await state.get_data()
    item_id = data["item_id"]
    item = db.get_item(item_id)
    promo = db.get_promocode(message.text.strip())

    if not item:
        await state.clear()
        await message.answer("Xizmat topilmadi.")
        return

    if not promo:
        kb = InlineKeyboardMarkup(inline_keyboard=[[back_button(f"item:{item_id}")]])
        await message.answer("❌ Bunday promokod topilmadi yoki faol emas.", reply_markup=kb)
        return

    new_price = max(0, item["price"] - promo["discount"])
    await state.clear()

    text = (
        f"🎟 Promokod qo'llandi!\n\n"
        f"📦 {item['name']}\n"
        f"~{item['price']:,} so'm~ → ".replace(",", " ") +
        f"<b>{new_price:,} so'm</b>\n\n".replace(",", " ") +
        f"Chegirma: {promo['discount']:,} so'm".replace(",", " ")
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Buyurtma berish (chegirma bilan)",
            callback_data=f"orderpromo:{item_id}:{promo['code']}"
        )],
        [back_button(f"item:{item_id}")],
    ])
    await message.answer(text, reply_markup=kb)


# ---------- BUYURTMA BERISH (ODDIY) ----------
@router.callback_query(F.data.startswith("order:"))
async def make_order(callback: CallbackQuery, bot: Bot):
    item_id = int(callback.data.split(":")[1])
    item = db.get_item(item_id)
    await send_order_notification(bot, callback.from_user, item, item["price"], None)
    await callback.answer("Buyurtmangiz qabul qilindi!", show_alert=False)
    await send_order_confirmation(bot, callback.from_user.id, item, item["price"])


# ---------- BUYURTMA BERISH (PROMOKOD BILAN) ----------
@router.callback_query(F.data.startswith("orderpromo:"))
async def make_order_promo(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split(":")
    item_id, code = int(parts[1]), parts[2]
    item = db.get_item(item_id)
    promo = db.get_promocode(code)
    final_price = max(0, item["price"] - promo["discount"]) if promo else item["price"]

    await send_order_notification(bot, callback.from_user, item, final_price, code)
    await callback.answer("Buyurtmangiz qabul qilindi!", show_alert=False)
    await send_order_confirmation(bot, callback.from_user.id, item, final_price)


async def send_order_notification(bot: Bot, user, item, final_price: int, promo_code):
    username_part = f"@{user.username}" if user.username else "username yo'q"
    text = (
        "🆕 Yangi buyurtma!\n\n"
        f"👤 Foydalanuvchi: {user.full_name} ({username_part})\n"
        f"🆔 ID: {user.id}\n\n"
        f"📦 Xizmat: {item['name']}\n"
        f"💵 Narxi: {final_price:,} so'm".replace(",", " ")
    )
    if promo_code:
        text += f"\n🎟 Promokod: {promo_code}"
    await bot.send_message(ADMIN_ID, text)


async def send_order_confirmation(bot: Bot, user_id: int, item, final_price: int):
    text = (
        f"{tge('check', '✔️')} Buyurtmangiz qabul qilindi!\n\n"
        f"📦 {item['name']} — {final_price:,} so'm".replace(",", " ") + "\n\n"
        "Tez orada admin siz bilan bog'lanadi."
    )
    await bot.send_message(user_id, text)
