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


class MurojaatState(StatesGroup):
    waiting_message = State()


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


# ---------- ASOSIY MENYU (doimiy, pastdagi tugmalar) ----------
BTN_SERVICES = "🛍 Xizmatlar"
BTN_MY_ORDERS = "🧾 Buyurtmalarim"
BTN_BALANCE = "💰 Hisobim"
BTN_TOPUP = "💳 Hisobni to'ldirish"
BTN_ADMIN = "👨‍💻 Admin"
BTN_SUPPORT = "✉️ Murojaat"

# Doimiy pastdagi tugmalarning matnlari to'plami. Har qanday joriy
# jarayonda (FSM holatida) foydalanuvchi shulardan birini bossa, joriy
# jarayon (masalan summani kiritish) NOTO'G'RI deb rad etilmasligi kerak -
# aksincha, tugma o'zining ishini bajarishi kerak. Shuning uchun har bir
# matn kiritish kutayotgan handler shu tugmalar UCHUN ISHLAMASLIGI kerak.
MAIN_MENU_BUTTONS = {BTN_SERVICES, BTN_MY_ORDERS, BTN_BALANCE, BTN_TOPUP, BTN_ADMIN, BTN_SUPPORT}
NOT_MENU_BUTTON = ~F.text.in_(MAIN_MENU_BUTTONS)


def main_reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_SERVICES), KeyboardButton(text=BTN_MY_ORDERS)],
            [KeyboardButton(text=BTN_BALANCE), KeyboardButton(text=BTN_TOPUP)],
            [KeyboardButton(text=BTN_ADMIN), KeyboardButton(text=BTN_SUPPORT)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


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
        await callback.message.answer(WELCOME_TEXT, reply_markup=main_reply_kb())
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

    await message.answer(WELCOME_TEXT, reply_markup=main_reply_kb())


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
    try:
        await callback.message.edit_text(
            "🏠 Asosiy menyu — pastdagi tugmalardan foydalaning 👇",
            reply_markup=None
        )
    except Exception:
        pass
    await callback.answer()


def build_contact_admin_content():
    admin_username = db.get_setting("admin_username")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Admin bilan yozish", url=f"https://t.me/{admin_username.lstrip('@')}", style="success")],
    ])
    return f"Admin bilan bog'lanish uchun: {admin_username}", kb


@router.message(F.text == BTN_ADMIN)
async def contact_admin_button(message: Message, state: FSMContext):
    await state.clear()
    text, kb = build_contact_admin_content()
    await message.answer(text, reply_markup=kb)


# ---------- BALANSNI TO'LDIRISH ----------
def build_topup_content(user_id: int):
    min_amount = db.get_setting("payment_min_amount") or "1000"
    balance = db.get_balance(user_id)
    text = (
        f"💰 Joriy balansingiz: <b>{balance:,} so'm</b>\n\n".replace(",", " ") +
        "💳 To'lov usuli: Uzcard/Humo (avto)\n\n"
        "💵 To'lov miqdorini kiriting:\n"
        f"⏩ Minimal: {int(min_amount):,} so'm".replace(",", " ")
    )
    return text, None


@router.message(F.text == BTN_TOPUP)
async def topup_button(message: Message, state: FSMContext):
    await state.set_state(TopupState.waiting_amount)
    text, kb = build_topup_content(message.from_user.id)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "menu:topup")
async def topup_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TopupState.waiting_amount)
    text, kb = build_topup_content(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ---------- HISOBIM ----------
@router.message(F.text == BTN_BALANCE)
async def balance_button(message: Message, state: FSMContext):
    await state.clear()
    balance = db.get_balance(message.from_user.id)
    order_count = len(db.get_user_orders(message.from_user.id))
    text = (
        "💰 <b>Hisobim</b>\n\n"
        f"Joriy balans: <b>{balance:,} so'm</b>\n".replace(",", " ") +
        f"Jami buyurtmalar: {order_count} ta"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Hisobni to'ldirish", callback_data="menu:topup", style="primary")]
    ])
    await message.answer(text, reply_markup=kb)


@router.message(TopupState.waiting_amount, NOT_MENU_BUTTON)
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


@router.message(TopupState.waiting_receipt, NOT_MENU_BUTTON)
async def topup_receipt_invalid(message: Message):
    await message.answer("❗️ Iltimos, to'lov chekini RASM shaklida yuboring.")


# ---------- XIZMATLAR (KATEGORIYALAR) ----------
async def build_services_screen():
    """Xizmatlar (asosiy) ekrani: nakrutka platformalari + Premium xizmatlarga
    o'tuvchi maxsus (admin tomonidan tahrirlanadigan nomli) tugma."""
    platforms = db.get_platforms()

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

    items_label = db.get_setting("items_button_label") or "⭐ Telegram xizmatlar"
    buttons.append([InlineKeyboardButton(text=items_label, callback_data="menu:items", style="primary")])

    if db.get_setting("top_offers_enabled") == "1":
        buttons.append([InlineKeyboardButton(text="🔥 Top takliflar", callback_data="menu:top", style="danger")])

    return "🛍 Kerakli xizmatni tanlang:", InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(F.text == BTN_SERVICES)
async def services_button(message: Message, state: FSMContext):
    await state.clear()
    text, kb = await build_services_screen()
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "menu:services")
async def services_callback(callback: CallbackQuery):
    text, kb = await build_services_screen()
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "menu:items")
async def show_categories(callback: CallbackQuery):
    categories = db.get_categories()

    if not categories:
        kb = InlineKeyboardMarkup(inline_keyboard=[[back_button("menu:services")]])
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
    buttons.append([back_button("menu:services")])

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


@router.message(PromoState.waiting_code, NOT_MENU_BUTTON)
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
async def make_order(callback: CallbackQuery):
    item_id = int(callback.data.split(":")[1])
    item = db.get_item(item_id)
    await show_order_confirmation(callback, item, item["price"], f"orderconfirm:{item_id}")


# ---------- BUYURTMA BERISH (PROMOKOD BILAN) ----------
@router.callback_query(F.data.startswith("orderpromo:"))
async def make_order_promo(callback: CallbackQuery):
    parts = callback.data.split(":")
    item_id, code = int(parts[1]), parts[2]
    item = db.get_item(item_id)
    promo = db.get_promocode(code)
    final_price = max(0, item["price"] - promo["discount"]) if promo else item["price"]
    await show_order_confirmation(callback, item, final_price, f"orderpromoconfirm:{item_id}:{code}")


async def show_order_confirmation(callback: CallbackQuery, item, final_price: int, confirm_callback: str):
    balance = db.get_balance(callback.from_user.id)
    text = (
        f"📦 {item['name']}\n\n"
        f"💵 Hisobingizdan <b>{final_price:,} so'm</b> yechib olinadi.\n".replace(",", " ") +
        f"💰 Joriy balansingiz: {balance:,} so'm\n\n".replace(",", " ") +
        "Tasdiqlaysizmi?"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha, tasdiqlayman", callback_data=confirm_callback, style="success"),
            InlineKeyboardButton(text="❌ Yo'q", callback_data=f"item:{item['id']}", style="danger"),
        ]
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("orderconfirm:"))
async def make_order_confirmed(callback: CallbackQuery, bot: Bot):
    item_id = int(callback.data.split(":")[1])
    item = db.get_item(item_id)
    await process_order(callback, bot, item, item["price"], None)


@router.callback_query(F.data.startswith("orderpromoconfirm:"))
async def make_order_promo_confirmed(callback: CallbackQuery, bot: Bot):
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
    order_id = await send_order_notification(bot, user, item, final_price, promo_code)
    await callback.answer("Buyurtmangiz qabul qilindi!", show_alert=False)
    await send_order_confirmation(bot, user.id, item, final_price, order_id)


async def send_order_notification(bot: Bot, user, item, final_price: int, promo_code):
    order_id = db.log_order(item["id"], user.id, final_price, promo_code, order_type="item", item_name=item["name"])

    username_part = f"@{user.username}" if user.username else "username yo'q"
    text = (
        "🆕 Yangi buyurtma!\n\n"
        f"🆔 Buyurtma raqami: #{order_id}\n\n"
        f"👤 Foydalanuvchi: {user.full_name} ({username_part})\n"
        f"🆔 Foydalanuvchi ID: {user.id}\n\n"
        f"📦 Xizmat: {item['name']}\n"
        f"💵 Narxi: {final_price:,} so'm".replace(",", " ") +
        "\n💰 Balansdan avtomatik yechildi.\n\n" +
        "⚠️ Tasdiqlaysizmi? (Bekor qilsangiz, mijozga pul avtomatik qaytariladi)"
    )
    if promo_code:
        text += f"\n🎟 Promokod: {promo_code}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"order_confirm:{order_id}", style="success"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"order_cancel:{order_id}", style="danger"),
        ]
    ])
    await notify_admin_text(bot, text, reply_markup=kb)
    return order_id


async def send_order_confirmation(bot: Bot, user_id: int, item, final_price: int, order_id: int):
    text = (
        f"{tge('check', '✔️')} Buyurtmangiz qabul qilindi!\n\n"
        f"🆔 Buyurtma raqami: #{order_id}\n"
        f"📦 {item['name']} — {final_price:,} so'm".replace(",", " ") + "\n\n"
        "Tez orada admin siz bilan bog'lanadi.\n"
        "Holatini «🧾 Buyurtmalarim» bo'limidan kuzatib borishingiz mumkin."
    )
    await bot.send_message(user_id, text)


# ---------- NAKRUTKA (SMM) XIZMATLARI ----------
# ---------- NAKRUTKA (SMM) XIZMATLARI ----------
# Platformalar endi to'g'ridan-to'g'ri "Xizmatlar" ekranida (build_services_screen)
# ko'rsatiladi, shuning uchun alohida "menu:smm" ekrani kerak emas.


@router.callback_query(F.data.startswith("smmcat:"))
async def show_smm_categories(callback: CallbackQuery):
    platform_id = int(callback.data.split(":")[1])
    platform = db.get_platform(platform_id)
    categories = db.get_smm_categories(platform_id)

    if not categories:
        kb = InlineKeyboardMarkup(inline_keyboard=[[back_button("menu:services")]])
        await callback.message.edit_text(
            f"«{platform['name']}» uchun hozircha kategoriya yo'q.",
            reply_markup=kb
        )
        await callback.answer()
        return

    buttons = [
        [InlineKeyboardButton(text=f"📂 {c['name']}", callback_data=f"smmsubcat:{c['id']}", style="success")]
        for c in categories
    ]
    buttons.append([back_button("menu:services")])

    await callback.message.edit_text(
        f"{platform['emoji']} {platform['name']} — kategoriyani tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("smmsubcat:"))
async def show_smm_services(callback: CallbackQuery):
    category_id = int(callback.data.split(":")[1])
    category = db.get_smm_category(category_id)
    platform = db.get_platform(category["platform_id"])
    services = db.get_smm_services_by_category(category_id)

    if not services:
        kb = InlineKeyboardMarkup(inline_keyboard=[[back_button(f"smmcat:{category['platform_id']}")]])
        await callback.message.edit_text(
            f"«{category['name']}» uchun hozircha xizmatlar yo'q.",
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
    buttons.append([back_button(f"smmcat:{category['platform_id']}")])

    await callback.message.edit_text(
        f"{platform['emoji']} {platform['name']} / 📂 {category['name']}:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


def build_smm_service_card(service, bot_username: str):
    text = (
        f"📦 {service['name']}\n\n"
        f"💵 Narxi: {service['price_per_1000']:,} so'm / 1000 dona\n".replace(",", " ") +
        f"🔽 Minimal: {service['min_qty']} — 🔼 Maksimal: {service['max_qty']}"
    )
    if service["average_time"]:
        text += f"\n⏰ Bajarilish vaqti: {service['average_time']}"
    share_link = f"https://t.me/{bot_username}?start=smmservice_{service['id']}"
    share_url = f"https://t.me/share/url?url={share_link}&text={service['name']}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↗️ Ulashish", url=share_url)],
        [InlineKeyboardButton(text="✅ Buyurtma berish", callback_data=f"smmorder:{service['id']}", style="success")],
        [back_button(f"smmsubcat:{service['category_id']}")],
    ])
    return text, kb


async def send_smm_service_card(message: Message, service_id: int, bot: Bot = None):
    service = db.get_smm_service(service_id)
    if not service:
        await message.answer("❌ Bunday xizmat topilmadi.", reply_markup=main_reply_kb())
        return
    me = await message.bot.get_me()
    text, kb = build_smm_service_card(service, me.username)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("smmservice:"))
async def smm_service_info(callback: CallbackQuery, state: FSMContext, bot: Bot):
    service_id = int(callback.data.split(":")[1])
    service = db.get_smm_service(service_id)
    me = await bot.get_me()
    text, kb = build_smm_service_card(service, me.username)
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


@router.message(SmmOrderState.waiting_link, NOT_MENU_BUTTON)
async def smm_order_link(message: Message, state: FSMContext):
    await state.update_data(link=message.text.strip())
    data = await state.get_data()
    service = db.get_smm_service(data["service_id"])
    await state.set_state(SmmOrderState.waiting_quantity)
    await message.answer(
        f"🔢 Miqdorni kiriting (raqam):\n"
        f"Minimal: {service['min_qty']} — Maksimal: {service['max_qty']}"
    )


@router.message(SmmOrderState.waiting_quantity, NOT_MENU_BUTTON)
async def smm_order_quantity(message: Message, state: FSMContext):
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

    await state.update_data(quantity=quantity, price=price)
    await state.set_state(SmmOrderState.confirming)

    text = (
        f"📦 {service['name']}\n"
        f"🔗 {data['link']}\n"
        f"🔢 Miqdor: {quantity}\n\n"
        f"💵 Hisobingizdan <b>{price:,} so'm</b> yechib olinadi.\n".replace(",", " ") +
        f"💰 Joriy balansingiz: {balance:,} so'm\n\n".replace(",", " ") +
        "Tasdiqlaysizmi?"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha, tasdiqlayman", callback_data="smmorderconfirm", style="success"),
            InlineKeyboardButton(text="❌ Yo'q", callback_data=f"smmservice:{service['id']}", style="danger"),
        ]
    ])
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "smmorderconfirm", SmmOrderState.confirming)
async def smm_order_confirmed(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    service = db.get_smm_service(data["service_id"])
    link = data["link"]
    quantity = data["quantity"]
    price = data["price"]
    await state.clear()

    # Panelga buyurtma yuboramiz
    result = smm_api.place_order(service["panel_service_id"], link, quantity)
    panel_order_id = result.get("order") if isinstance(result, dict) else None

    if not panel_order_id:
        error_msg = result.get("error", "Noma'lum xatolik") if isinstance(result, dict) else "Noma'lum xatolik"
        await callback.message.edit_text(
            f"❌ Buyurtma yuborishda xatolik yuz berdi: {error_msg}\n\n"
            "Balansingizdan pul yechilmadi. Iltimos, keyinroq qayta urinib ko'ring yoki admin bilan bog'laning."
        )
        await callback.answer()
        return

    db.add_balance(callback.from_user.id, -price)
    order_id = db.log_order(
        item_id=None, user_id=callback.from_user.id, price=price, promo_code=None,
        order_type="smm", item_name=service["name"], link=link,
        quantity=quantity, panel_order_id=panel_order_id
    )

    await callback.message.edit_text(
        f"{tge('check', '✔️')} Buyurtma qabul qilindi!\n\n"
        f"🆔 Buyurtma raqami: #{order_id}\n\n"
        f"📦 {service['name']}\n"
        f"🔗 {link}\n"
        f"🔢 Miqdor: {quantity}\n"
        f"💵 Narxi: {price:,} so'm\n".replace(",", " ") +
        "\nBuyurtmangiz bajarilishi biroz vaqt olishi mumkin.\n"
        "Holatini «🧾 Buyurtmalarim» bo'limidan kuzatib borishingiz mumkin."
    )

    user = callback.from_user
    username_part = f"@{user.username}" if user.username else "username yo'q"
    text = (
        "📈 Yangi nakrutka buyurtmasi!\n\n"
        f"🆔 Buyurtma raqami: #{order_id}\n\n"
        f"👤 {user.full_name} ({username_part})\n"
        f"🆔 Foydalanuvchi ID: {user.id}\n\n"
        f"📦 {service['name']}\n"
        f"🔗 {link}\n"
        f"🔢 Miqdor: {quantity}\n"
        f"💵 Narxi: {price:,} so'm\n".replace(",", " ") +
        f"🆔 Panel buyurtma raqami: {panel_order_id}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Xpanel holatini tekshirish", callback_data=f"order_check_panel:{order_id}", style="primary")],
        [InlineKeyboardButton(text="❌ Bekor qilish (pulni qaytarish)", callback_data=f"order_cancel:{order_id}", style="danger")],
    ])
    await notify_admin_text(bot, text, reply_markup=kb)
    await callback.answer()


# ---------- BUYURTMALARIM ----------
STATUS_LABELS = {
    "yangi": "🟡 Jarayonda",
    "bajarildi": "🟢 Bajarildi",
    "bekor qilindi": "🔴 Bekor qilindi",
}
ORDERS_PAGE_SIZE = 5


def build_my_orders_content(user_id: int, page: int = 0):
    orders = db.get_user_orders(user_id)

    if not orders:
        return "Sizda hozircha buyurtmalar yo'q.", None

    start = page * ORDERS_PAGE_SIZE
    chunk = orders[start:start + ORDERS_PAGE_SIZE]
    total_pages = (len(orders) - 1) // ORDERS_PAGE_SIZE + 1

    text = f"🧾 <b>Buyurtmalarim</b> ({page + 1}/{total_pages})\n\n"
    for o in chunk:
        status = STATUS_LABELS.get(o["status"], o["status"])
        text += (
            f"🆔 #{o['id']} — {o['item_name'] or ''}\n"
            f"💵 {o['price']:,} so'm — {status}\n\n".replace(",", " ")
        )

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"myorders_page:{page - 1}", style="danger"))
    if start + ORDERS_PAGE_SIZE < len(orders):
        nav.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"myorders_page:{page + 1}", style="success"))

    kb = InlineKeyboardMarkup(inline_keyboard=[nav]) if nav else None
    return text, kb


@router.message(F.text == BTN_MY_ORDERS)
async def my_orders_button(message: Message, state: FSMContext):
    await state.clear()
    text, kb = build_my_orders_content(message.from_user.id, page=0)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "menu:myorders")
async def my_orders(callback: CallbackQuery):
    text, kb = build_my_orders_content(callback.from_user.id, page=0)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("myorders_page:"))
async def my_orders_page_nav(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    text, kb = build_my_orders_content(callback.from_user.id, page=page)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ---------- TEZKOR BUYRUQLAR (/pay, /orders, /admin, /top) ----------
async def _require_ready(message: Message) -> bool:
    """Bloklanmagan, telefoni tasdiqlangan va obunani o'tgan foydalanuvchimi - tekshiradi."""
    if db.is_blocked(message.from_user.id):
        await message.answer("⛔️ Siz botdan foydalanish huquqidan mahrum qilingansiz.")
        return False
    if not db.has_phone(message.from_user.id):
        await message.answer(PHONE_REQUEST_TEXT, reply_markup=phone_request_kb())
        return False
    return True


@router.message(Command("pay"))
async def cmd_pay(message: Message, state: FSMContext):
    if not await _require_ready(message):
        return
    await state.set_state(TopupState.waiting_amount)
    text, kb = build_topup_content(message.from_user.id)
    await message.answer(text, reply_markup=kb)


@router.message(Command("orders"))
async def cmd_orders(message: Message):
    if not await _require_ready(message):
        return
    text, kb = build_my_orders_content(message.from_user.id)
    await message.answer(text, reply_markup=kb)


@router.message(Command("admin"))
async def cmd_contact_admin(message: Message):
    if not await _require_ready(message):
        return
    text, kb = build_contact_admin_content()
    await message.answer(text, reply_markup=kb)


@router.message(Command("top"))
async def cmd_top(message: Message):
    if not await _require_ready(message):
        return
    text, kb = build_top_offers_content()
    await message.answer(text, reply_markup=kb)


# ---------- MUROJAAT (admin bilan bot orqali yozishma) ----------
@router.message(F.text == BTN_SUPPORT)
async def support_button(message: Message, state: FSMContext):
    await state.set_state(MurojaatState.waiting_message)
    await message.answer("✉️ Xabaringizni yozing, adminga yetkazamiz:")


@router.message(MurojaatState.waiting_message, NOT_MENU_BUTTON)
async def support_message_received(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user = message.from_user
    username_part = f"@{user.username}" if user.username else "username yo'q"

    text = (
        "✉️ <b>Yangi murojaat!</b>\n\n"
        f"👤 Foydalanuvchi: {user.full_name} ({username_part})\n"
        f"🆔 ID: {user.id}\n\n"
        f"💬 Xabar:\n{message.text or '(matn emas xabar)'}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Javob berish", callback_data=f"reply_user:{user.id}", style="primary")]
    ])
    await notify_admin_text(bot, text, reply_markup=kb)
    await message.answer("✅ Xabaringiz adminga yuborildi. Tez orada javob beriladi.")
