# handlers_user.py
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
import smm_api
from config import ADMIN_ID

router = Router()


# ---------- FSM ----------
class PromoState(StatesGroup):
    item_id = State()
    waiting_code = State()


class TopupState(StatesGroup):
    waiting_amount = State()
    waiting_receipt = State()


class SmmOrderState(StatesGroup):
    service_id = State()
    waiting_link = State()
    waiting_quantity = State()


# ---------- Premium (maxsus animatsion) emojilar ----------
CUSTOM_EMOJI = {
    "wave": "5472235990955334730",       # 👋
    "new": "5382357040008021292",        # 🆕
    "fire": "5424972470023104089",       # 🔥
    "check": "5206607081334906820",      # ✔️
    "exclaim": "5440660757194744323",    # ‼️
    "bag": "5406683434124859552",        # 🛍
    "soon": "5440621591387980068",       # 🔜
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
        [InlineKeyboardButton(text=f"{e_services} Xizmatlar", callback_data="menu:services", style="primary")],
        [InlineKeyboardButton(text=f"{e_top} Top takliflar", callback_data="menu:top", style="danger")],
        [InlineKeyboardButton(text="📈 Nakrutka xizmati", callback_data="menu:smm", style="primary")],
        [InlineKeyboardButton(text="💳 Balansni to'ldirish", callback_data="menu:topup", style="primary")],
        [InlineKeyboardButton(text=f"{e_contact} Admin bilan aloqa", callback_data="menu:contact", style="success")],
        [InlineKeyboardButton(text=f"{e_channel} Bizning kanal", url=channel_url)],
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

PHONE_REQUEST_TEXT = (
    "🔒 Xavfsizlik maqsadida, davom etishdan oldin telefon raqamingizni tasdiqlashingiz kerak.\n\n"
    "Pastdagi tugmani bosib, raqamingizni yuboring 👇"
)


def phone_request_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


@router.message(CommandStart())
async def cmd_start(message: Message):
    db.add_user(message.from_user.id)

    if db.is_blocked(message.from_user.id):
        await message.answer("⛔️ Siz botdan foydalanish huquqidan mahrum qilingansiz.")
        return

    if not db.has_phone(message.from_user.id):
        await message.answer(PHONE_REQUEST_TEXT, reply_markup=phone_request_kb())
        return

    await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())


@router.message(F.contact)
async def contact_received(message: Message):
    if message.contact.user_id != message.from_user.id:
        await message.answer("❗️ Iltimos, faqat o'zingizning raqamingizni yuboring.")
        return

    db.save_user_info(
        message.from_user.id,
        phone=message.contact.phone_number,
        full_name=message.from_user.full_name,
        username=message.from_user.username
    )
    await message.answer("✅ Raqamingiz tasdiqlandi!", reply_markup=ReplyKeyboardRemove())
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())


@router.callback_query(F.data == "menu:main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.edit_text(WELCOME_TEXT, reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "menu:contact")
async def contact_admin(callback: CallbackQuery):
    admin_username = db.get_setting("admin_username")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Admin bilan yozish", url=f"https://t.me/{admin_username.lstrip('@')}", style="success")],
        [back_button("menu:main")],
    ])
    await callback.message.edit_text(
        f"Admin bilan bog'lanish uchun: {admin_username}",
        reply_markup=kb
    )
    await callback.answer()


# ---------- BALANSNI TO'LDIRISH ----------
@router.callback_query(F.data == "menu:topup")
async def topup_start(callback: CallbackQuery, state: FSMContext):
    min_amount = db.get_setting("payment_min_amount") or "1000"
    balance = db.get_balance(callback.from_user.id)
    await state.set_state(TopupState.waiting_amount)
    kb = InlineKeyboardMarkup(inline_keyboard=[[back_button("menu:main")]])
    await callback.message.edit_text(
        f"💰 Joriy balansingiz: <b>{balance:,} so'm</b>\n\n".replace(",", " ") +
        "💳 To'lov usuli: Uzcard/Humo (avto)\n\n"
        "💵 To'lov miqdorini kiriting:\n"
        f"⏩ Minimal: {int(min_amount):,} so'm".replace(",", " "),
        reply_markup=kb
    )
    await callback.answer()


@router.message(TopupState.waiting_amount)
async def topup_amount(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("❗️ Iltimos, faqat raqam kiriting.")
        return

    amount = int(message.text.strip())
    min_amount = int(db.get_setting("payment_min_amount") or "1000")
    if amount < min_amount:
        await message.answer(f"❗️ Minimal summa {min_amount:,} so'm".replace(",", " "))
        return

    await state.update_data(amount=amount)
    await state.set_state(TopupState.waiting_receipt)

    card_number = db.get_setting("payment_card_number")
    card_owner = db.get_setting("payment_card_owner")
    await message.answer(
        f"💳 Karta raqami: <code>{card_number}</code>\n"
        f"👤 Egasi: {card_owner}\n\n"
        f"Summani ({amount:,} so'm) shu kartaga o'tkazing.\n".replace(",", " ") +
        "📝 To'lov chekini (rasm) yuboring:"
    )


@router.message(TopupState.waiting_receipt, F.photo)
async def topup_receipt(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    amount = data["amount"]
    await state.clear()

    receipt_file_id = message.photo[-1].file_id
    topup_id = db.create_topup(message.from_user.id, amount, receipt_file_id)

    await message.answer(
        "✅ Qabul qilindi.\n\n"
        "<i>To'lov cheki 15-60 daqiqa ichida tekshiriladi!</i>"
    )

    user = message.from_user
    username_part = f"@{user.username}" if user.username else "username yo'q"
    caption = (
        "💳 Yangi balans to'ldirish so'rovi!\n\n"
        f"👤 Foydalanuvchi: {user.full_name} ({username_part})\n"
        f"🆔 ID: {user.id}\n"
        f"💵 Summa: {amount:,} so'm".replace(",", " ")
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"topup_ok:{topup_id}", style="success"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"topup_no:{topup_id}", style="danger"),
        ]
    ])
    await bot.send_photo(ADMIN_ID, receipt_file_id, caption=caption, reply_markup=kb)


@router.message(TopupState.waiting_receipt)
async def topup_receipt_invalid(message: Message):
    await message.answer("❗️ Iltimos, to'lov chekini RASM shaklida yuboring.")


# ---------- XIZMATLAR (KATEGORIYALAR) ----------
@router.callback_query(F.data == "menu:services")
async def show_categories(callback: CallbackQuery):
    categories = db.get_categories()

    if not categories:
        kb = InlineKeyboardMarkup(inline_keyboard=[[back_button("menu:main")]])
        await callback.message.edit_text(
            f"Hozircha xizmatlar qo'shilmagan. Tez orada qo'shiladi. {tge('soon', '🔜')}",
            reply_markup=kb
        )
        await callback.answer()
        return

    buttons = [
        [InlineKeyboardButton(text=cat["name"], callback_data=f"cat:{cat['id']}", style="success")]
        for cat in categories
    ]
    buttons.append([back_button("menu:main")])

    header = f"{tge('new', '🆕')} Kerakli xizmat turini tanlang:"
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
            callback_data=f"item:{item['id']}",
            style="danger"
        )]
        for item in items
    ]
    buttons.append([back_button("menu:main")])

    header = f"{tge('bag', '🛍')} {tge('fire', '🔥')} <b>Top takliflar</b>:"
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
            callback_data=f"item:{item['id']}",
            style="danger" if item["is_top"] else None
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
        [InlineKeyboardButton(text=f"{e_order} Buyurtma berish", callback_data=f"order:{item['id']}", style="success")],
        [InlineKeyboardButton(text="🎟 Promokod kiritish", callback_data=f"promo:{item['id']}", style="primary")],
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
            callback_data=f"orderpromo:{item_id}:{promo['code']}",
            style="success"
        )],
        [back_button(f"item:{item_id}")],
    ])
    await message.answer(text, reply_markup=kb)


# ---------- BUYURTMA BERISH (ODDIY) ----------
@router.callback_query(F.data.startswith("order:"))
async def make_order(callback: CallbackQuery, bot: Bot):
    item_id = int(callback.data.split(":")[1])
    item = db.get_item(item_id)
    await process_order(callback, bot, item, item["price"], None)


# ---------- BUYURTMA BERISH (PROMOKOD BILAN) ----------
@router.callback_query(F.data.startswith("orderpromo:"))
async def make_order_promo(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split(":")
    item_id, code = int(parts[1]), parts[2]
    item = db.get_item(item_id)
    promo = db.get_promocode(code)
    final_price = max(0, item["price"] - promo["discount"]) if promo else item["price"]
    await process_order(callback, bot, item, final_price, code)


async def process_order(callback: CallbackQuery, bot: Bot, item, final_price: int, promo_code):
    user = callback.from_user
    balance = db.get_balance(user.id)

    if balance < final_price:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Balansni to'ldirish", callback_data="menu:topup", style="primary")]
        ])
        await callback.message.edit_text(
            f"❌ Balansingiz yetarli emas.\n\n"
            f"Kerak: {final_price:,} so'm\n".replace(",", " ") +
            f"Sizda: {balance:,} so'm".replace(",", " "),
            reply_markup=kb
        )
        await callback.answer()
        return

    db.add_balance(user.id, -final_price)
    await send_order_notification(bot, user, item, final_price, promo_code)
    await callback.answer("Buyurtmangiz qabul qilindi!", show_alert=False)
    await send_order_confirmation(bot, user.id, item, final_price)


async def send_order_notification(bot: Bot, user, item, final_price: int, promo_code):
    db.log_order(item["id"], user.id, final_price, promo_code)

    username_part = f"@{user.username}" if user.username else "username yo'q"
    text = (
        "🆕 Yangi buyurtma!\n\n"
        f"👤 Foydalanuvchi: {user.full_name} ({username_part})\n"
        f"🆔 ID: {user.id}\n\n"
        f"📦 Xizmat: {item['name']}\n"
        f"💵 Narxi: {final_price:,} so'm".replace(",", " ") +
        "\n💰 Balansdan avtomatik yechildi."
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


# ---------- NAKRUTKA (SMM) XIZMATLARI ----------
@router.callback_query(F.data == "menu:smm")
async def show_platforms(callback: CallbackQuery):
    platforms = db.get_platforms()

    if not platforms:
        kb = InlineKeyboardMarkup(inline_keyboard=[[back_button("menu:main")]])
        await callback.message.edit_text(
            "Hozircha nakrutka xizmatlari qo'shilmagan.",
            reply_markup=kb
        )
        await callback.answer()
        return

    # 2 tadan qator qilib joylashtiramiz (skrindagi ko'rinishga o'xshab)
    buttons = []
    row = []
    for p in platforms:
        row.append(InlineKeyboardButton(
            text=f"{p['emoji']} {p['name']}", callback_data=f"smmcat:{p['id']}", style="success"
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([back_button("menu:main")])

    await callback.message.edit_text(
        "📈 Qaysi platforma uchun xizmat kerak?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("smmcat:"))
async def show_smm_services(callback: CallbackQuery):
    platform_id = int(callback.data.split(":")[1])
    platform = db.get_platform(platform_id)
    services = db.get_smm_services_by_platform(platform_id)

    if not services:
        kb = InlineKeyboardMarkup(inline_keyboard=[[back_button("menu:smm")]])
        await callback.message.edit_text(
            f"«{platform['name']}» uchun hozircha xizmatlar yo'q.",
            reply_markup=kb
        )
        await callback.answer()
        return

    buttons = [
        [InlineKeyboardButton(
            text=f"{s['name']} — {s['price_per_1000']:,} so'm/1000".replace(",", " "),
            callback_data=f"smmservice:{s['id']}",
            style="success"
        )]
        for s in services
    ]
    buttons.append([back_button("menu:smm")])

    await callback.message.edit_text(
        f"{platform['emoji']} {platform['name']} xizmatlari:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("smmservice:"))
async def smm_service_info(callback: CallbackQuery, state: FSMContext):
    service_id = int(callback.data.split(":")[1])
    service = db.get_smm_service(service_id)

    text = (
        f"📦 {service['name']}\n\n"
        f"💵 Narxi: {service['price_per_1000']:,} so'm / 1000 dona\n".replace(",", " ") +
        f"🔢 Minimal: {service['min_qty']} — Maksimal: {service['max_qty']}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Buyurtma berish", callback_data=f"smmorder:{service_id}", style="success")],
        [back_button(f"smmcat:{service['platform_id']}")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("smmorder:"))
async def smm_order_start(callback: CallbackQuery, state: FSMContext):
    service_id = int(callback.data.split(":")[1])
    await state.update_data(service_id=service_id)
    await state.set_state(SmmOrderState.waiting_link)
    kb = InlineKeyboardMarkup(inline_keyboard=[[back_button(f"smmservice:{service_id}")]])
    await callback.message.edit_text(
        "🔗 Havola yoki username yuboring (masalan: https://t.me/kanal):",
        reply_markup=kb
    )
    await callback.answer()


@router.message(SmmOrderState.waiting_link)
async def smm_order_link(message: Message, state: FSMContext):
    await state.update_data(link=message.text.strip())
    data = await state.get_data()
    service = db.get_smm_service(data["service_id"])
    await state.set_state(SmmOrderState.waiting_quantity)
    await message.answer(
        f"🔢 Miqdorni kiriting (raqam):\n"
        f"Minimal: {service['min_qty']} — Maksimal: {service['max_qty']}"
    )


@router.message(SmmOrderState.waiting_quantity)
async def smm_order_quantity(message: Message, state: FSMContext, bot: Bot):
    if not message.text.strip().isdigit():
        await message.answer("❗️ Iltimos, faqat raqam kiriting.")
        return

    quantity = int(message.text.strip())
    data = await state.get_data()
    service = db.get_smm_service(data["service_id"])

    if quantity < service["min_qty"] or quantity > service["max_qty"]:
        await message.answer(
            f"❗️ Miqdor {service['min_qty']} dan {service['max_qty']} gacha bo'lishi kerak."
        )
        return

    price = round(service["price_per_1000"] * quantity / 1000)
    balance = db.get_balance(message.from_user.id)

    if balance < price:
        await state.clear()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Balansni to'ldirish", callback_data="menu:topup", style="primary")]
        ])
        await message.answer(
            f"❌ Balansingiz yetarli emas.\n\n"
            f"Kerak: {price:,} so'm\n".replace(",", " ") +
            f"Sizda: {balance:,} so'm".replace(",", " "),
            reply_markup=kb
        )
        return

    link = data["link"]
    await state.clear()

    # Panelga buyurtma yuboramiz
    result = smm_api.place_order(service["panel_service_id"], link, quantity)
    panel_order_id = result.get("order") if isinstance(result, dict) else None

    if not panel_order_id:
        error_msg = result.get("error", "Noma'lum xatolik") if isinstance(result, dict) else "Noma'lum xatolik"
        await message.answer(
            f"❌ Buyurtma yuborishda xatolik yuz berdi: {error_msg}\n\n"
            "Balansingizdan pul yechilmadi. Iltimos, keyinroq qayta urinib ko'ring yoki admin bilan bog'laning."
        )
        return

    db.add_balance(message.from_user.id, -price)
    db.create_smm_order(message.from_user.id, service["id"], link, quantity, price, panel_order_id)

    await message.answer(
        f"{tge('check', '✔️')} Buyurtma qabul qilindi!\n\n"
        f"📦 {service['name']}\n"
        f"🔗 {link}\n"
        f"🔢 Miqdor: {quantity}\n"
        f"💵 Narxi: {price:,} so'm\n".replace(",", " ") +
        f"🆔 Buyurtma raqami: {panel_order_id}\n\n" +
        "Buyurtmangiz bajarilishi biroz vaqt olishi mumkin."
    )

    user = message.from_user
    username_part = f"@{user.username}" if user.username else "username yo'q"
    await bot.send_message(
        ADMIN_ID,
        "📈 Yangi nakrutka buyurtmasi!\n\n"
        f"👤 {user.full_name} ({username_part})\n"
        f"🆔 ID: {user.id}\n\n"
        f"📦 {service['name']}\n"
        f"🔗 {link}\n"
        f"🔢 Miqdor: {quantity}\n"
        f"💵 Narxi: {price:,} so'm\n".replace(",", " ") +
        f"🆔 Panel buyurtma raqami: {panel_order_id}"
    )
