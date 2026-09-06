# handlers_user.py
import logging
from aiogram import Router, F, Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
import smm_api
from config import ADMIN_ID, BOT_TOKEN, ADMIN_BOT_TOKEN

router = Router()


# ---------- Admin botiga xabar yuborish uchun yordamchi ----------
# Buyurtma xabarlari endi (agar sozlangan bo'lsa) ALOHIDA admin bot orqali
# adminning shaxsiy chatiga keladi, mijozlar boti orqali emas.
_admin_notifier_bot = None
_admin_notify_log = logging.getLogger("admin_notify")


def get_admin_notifier_bot(fallback_bot: Bot) -> Bot:
    global _admin_notifier_bot
    if ADMIN_BOT_TOKEN:
        if _admin_notifier_bot is None:
            _admin_notifier_bot = Bot(token=ADMIN_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        return _admin_notifier_bot
    return fallback_bot


async def notify_admin_text(fallback_bot: Bot, text: str, reply_markup=None):
    """Admin botiga xabar yuboradi; muvaffaqiyatsiz bo'lsa, asosiy bot orqali yuboradi."""
    notifier = get_admin_notifier_bot(fallback_bot)
    try:
        await notifier.send_message(ADMIN_ID, text, reply_markup=reply_markup)
    except Exception as e:
        _admin_notify_log.error(f"Admin botiga xabar yuborilmadi: {e}")
        if notifier is not fallback_bot:
            try:
                await fallback_bot.send_message(ADMIN_ID, text, reply_markup=reply_markup)
            except Exception as e2:
                _admin_notify_log.error(f"Zaxira orqali ham yuborilmadi: {e2}")


async def notify_admin_photo(fallback_bot: Bot, photo_bytes: bytes, caption: str, reply_markup=None):
    """photo_bytes - allaqachon yuklab olingan xom rasm baytlari (file_id EMAS,
    chunki file_id botlar orasida ishlamaydi)."""
    from aiogram.types import BufferedInputFile
    notifier = get_admin_notifier_bot(fallback_bot)
    try:
        photo = BufferedInputFile(photo_bytes, filename="chek.jpg")
        await notifier.send_photo(ADMIN_ID, photo, caption=caption, reply_markup=reply_markup)
    except Exception as e:
        _admin_notify_log.error(f"Admin botiga rasm yuborilmadi: {e}")
        if notifier is not fallback_bot:
            try:
                photo = BufferedInputFile(photo_bytes, filename="chek.jpg")
                await fallback_bot.send_photo(ADMIN_ID, photo, caption=caption, reply_markup=reply_markup)
            except Exception as e2:
                _admin_notify_log.error(f"Zaxira orqali ham yuborilmadi: {e2}")


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
    confirming = State()


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
    top_enabled = db.get_setting("top_offers_enabled") == "1"

    row1 = [InlineKeyboardButton(text=f"{e_services} Xizmatlar", callback_data="menu:services", style="primary")]
    if top_enabled:
        row1.append(InlineKeyboardButton(text=f"{e_top} Top takliflar", callback_data="menu:top", style="danger"))

    rows = [
        row1,
        [
            InlineKeyboardButton(text="📈 Nakrutka xizmati", callback_data="menu:smm", style="primary"),
            InlineKeyboardButton(text="🧾 Buyurtmalarim", callback_data="menu:myorders", style="primary"),
        ],
        [
            InlineKeyboardButton(text="💳 Balansni to'ldirish", callback_data="menu:topup", style="primary"),
            InlineKeyboardButton(text=f"{e_contact} Admin bilan aloqa", callback_data="menu:contact", style="success"),
        ],
        [InlineKeyboardButton(text=f"{e_channel} Bizning kanal", url=channel_url)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


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


# ---------- MAJBURIY OBUNA ----------
async def is_subscribed(bot: Bot, user_id: int) -> bool:
    enabled = db.get_setting("require_channel_enabled")
    if enabled != "1":
        return True
    channel = db.get_setting("require_channel_username")
    if not channel:
        return True
    try:
        member = await bot.get_chat_member(channel, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return True  # bot admin emas yoki xato bo'lsa, botni bloklab qo'ymaymiz


def subscribe_kb() -> InlineKeyboardMarkup:
    channel_url = db.get_setting("require_channel_url") or "https://t.me"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanalga o'tish", url=channel_url, style="primary")],
        [InlineKeyboardButton(text="✅ Tekshirdim", callback_data="check_subscription", style="success")],
    ])


SUBSCRIBE_TEXT = "🔒 Botdan foydalanish uchun avval kanalimizga a'zo bo'ling, so'ng «✅ Tekshirdim» tugmasini bosing."


class SubscriptionMiddleware:
    """Har bir tugma bosilganda (callback_query) majburiy obunani tekshiradi."""
    async def __call__(self, handler, event: CallbackQuery, data):
        if event.data == "check_subscription":
            return await handler(event, data)
        bot: Bot = data["bot"]
        if not await is_subscribed(bot, event.from_user.id):
            await event.answer()
            await event.message.answer(SUBSCRIBE_TEXT, reply_markup=subscribe_kb())
            return
        return await handler(event, data)


router.callback_query.middleware(SubscriptionMiddleware())


@router.callback_query(F.data == "check_subscription")
async def check_subscription_cb(callback: CallbackQuery, bot: Bot):
    if await is_subscribed(bot, callback.from_user.id):
        await callback.message.delete()
        await callback.message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())
    else:
        await callback.answer("❗️ Hali kanalga a'zo bo'lmagansiz.", show_alert=True)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext, bot: Bot):
    db.add_user(message.from_user.id)

    if db.is_blocked(message.from_user.id):
        await message.answer("⛔️ Siz botdan foydalanish huquqidan mahrum qilingansiz.")
        return

    if command.args:
        await state.update_data(pending_start=command.args)

    if not db.has_phone(message.from_user.id):
        await message.answer(PHONE_REQUEST_TEXT, reply_markup=phone_request_kb())
        return

    if not await is_subscribed(bot, message.from_user.id):
        await message.answer(SUBSCRIBE_TEXT, reply_markup=subscribe_kb())
        return

    await open_start_target(message, state)


async def open_start_target(message: Message, state: FSMContext):
    """Agar deep-link orqali kirilgan bo'lsa (masalan ulashilgan xizmat), to'g'ridan-to'g'ri o'sha yerga olib boradi."""
    data = await state.get_data()
    payload = data.get("pending_start")
    if payload:
        await state.update_data(pending_start=None)
        if payload.startswith("smmservice_"):
            service_id = payload.replace("smmservice_", "")
            if service_id.isdigit():
                await send_smm_service_card(message, int(service_id))
                return

    await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())


@router.message(F.contact)
async def contact_received(message: Message, state: FSMContext, bot: Bot):
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

    if not await is_subscribed(bot, message.from_user.id):
        await message.answer(SUBSCRIBE_TEXT, reply_markup=subscribe_kb())
        return

    await open_start_target(message, state)


@router.callback_query(F.data == "menu:main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.edit_text(WELCOME_TEXT, reply_markup=main_menu_kb())
    await callback.answer()


def build_contact_admin_content():
    admin_username = db.get_setting("admin_username")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Admin bilan yozish", url=f"https://t.me/{admin_username.lstrip('@')}", style="success")],
        [back_button("menu:main")],
    ])
    return f"Admin bilan bog'lanish uchun: {admin_username}", kb


@router.callback_query(F.data == "menu:contact")
async def contact_admin(callback: CallbackQuery):
    text, kb = build_contact_admin_content()
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ---------- BALANSNI TO'LDIRISH ----------
def build_topup_content(user_id: int):
    min_amount = db.get_setting("payment_min_amount") or "1000"
    balance = db.get_balance(user_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[back_button("menu:main")]])
    text = (
        f"💰 Joriy balansingiz: <b>{balance:,} so'm</b>\n\n".replace(",", " ") +
        "💳 To'lov usuli: Uzcard/Humo (avto)\n\n"
        "💵 To'lov miqdorini kiriting:\n"
        f"⏩ Minimal: {int(min_amount):,} so'm".replace(",", " ")
    )
    return text, kb


@router.callback_query(F.data == "menu:topup")
async def topup_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TopupState.waiting_amount)
    text, kb = build_topup_content(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=kb)
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

    # Rasmning file_id'si faqat MIJOZLAR botida ishlaydi (mijoz shu botga
    # yuborgan). Admin botiga yuborish uchun rasmni hoziroq yuklab olamiz,
    # keyin admin botiga XOM BAYT sifatida qayta yuklaymiz.
    try:
        file_bytes = await bot.download(receipt_file_id)
        await notify_admin_photo(bot, file_bytes.read(), caption, reply_markup=kb)
    except Exception as e:
        _admin_notify_log.error(f"Chekni yuklab olishda xatolik: {e}")
        await notify_admin_text(bot, caption + "\n\n⚠️ Chek rasmini yuklab bo'lmadi.", reply_markup=kb)


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
def build_top_offers_content():
    """(matn, klaviatura) qaytaradi. Agar Top o'chirilgan yoki bo'sh bo'lsa ham ishlaydi."""
    if db.get_setting("top_offers_enabled") != "1":
        kb = InlineKeyboardMarkup(inline_keyboard=[[back_button("menu:main")]])
        return "Hozircha Top takliflar bo'limi o'chirilgan.", kb

    items = db.get_top_items()
    smm_services = db.get_top_smm_services()

    if not items and not smm_services:
        kb = InlineKeyboardMarkup(inline_keyboard=[[back_button("menu:main")]])
        return "Hozircha Top takliflar belgilanmagan.", kb

    buttons = []
    for item in items:
        buttons.append([InlineKeyboardButton(
            text=f"🔥 {item['name']} — {item['price']:,} so'm".replace(",", " "),
            callback_data=f"item:{item['id']}",
            style="danger"
        )])
    for s in smm_services:
        buttons.append([InlineKeyboardButton(
            text=f"🔥 {s['name']} — {s['price_per_1000']:,} so'm/1000".replace(",", " "),
            callback_data=f"smmservice:{s['id']}",
            style="danger"
        )])
    buttons.append([back_button("menu:main")])

    header = f"{tge('bag', '🛍')} {tge('fire', '🔥')} <b>Top takliflar</b>:"
    return header, InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "menu:top")
async def show_top_items(callback: CallbackQuery):
    text, kb = build_top_offers_content()
    await callback.message.edit_text(text, reply_markup=kb)
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
    item_id = d
