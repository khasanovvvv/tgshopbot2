# handlers_admin.py
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
import smm_api
from config import ADMIN_ID
from handlers_user import tge

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


# ---------- FSM HOLATLARI ----------
class AddCategory(StatesGroup):
    name = State()


class AddItem(StatesGroup):
    category_id = State()
    name = State()
    price = State()
    info = State()


class EditPrice(StatesGroup):
    item_id = State()
    new_price = State()


class RenameCategory(StatesGroup):
    category_id = State()
    new_name = State()


class EditSettings(StatesGroup):
    admin_username = State()
    channel_url = State()


class EditEmoji(StatesGroup):
    key = State()
    new_emoji = State()


class BroadcastState(StatesGroup):
    waiting_content = State()


class AddPromo(StatesGroup):
    code = State()
    discount = State()


class FindUser(StatesGroup):
    waiting_id = State()


class AdjustBalance(StatesGroup):
    user_id = State()
    mode = State()  # "add" yoki "subtract"
    amount = State()


class PaymentSettings(StatesGroup):
    card_number = State()
    card_owner = State()
    min_amount = State()


class AddPlatform(StatesGroup):
    name = State()
    emoji = State()


class SearchPanelServices(StatesGroup):
    keyword = State()


class AddSmmService(StatesGroup):
    platform_id = State()
    panel_service_id = State()
    confirm_info = State()
    name = State()
    price = State()
    min_qty = State()
    max_qty = State()


class RequiredChannel(StatesGroup):
    username = State()
    url = State()


# ---------- ADMIN ASOSIY MENYU ----------
def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kategoriya qo'shish", callback_data="admin:add_cat", style="primary")],
        [InlineKeyboardButton(text="📂 Kategoriyalarni boshqarish", callback_data="admin:categories", style="success")],
        [InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin:users", style="success")],
        [InlineKeyboardButton(text="📈 Nakrutka xizmatlari", callback_data="admin:smm", style="success")],
        [InlineKeyboardButton(text="💳 To'lov sozlamalari", callback_data="admin:payment_settings", style="success")],
        [InlineKeyboardButton(text="🔒 Majburiy obuna", callback_data="admin:required_channel", style="success")],
        [InlineKeyboardButton(text="🎟 Promokodlar", callback_data="admin:promos", style="success")],
        [InlineKeyboardButton(text="📢 Reklama yuborish", callback_data="admin:broadcast", style="success")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin:stats", style="success")],
        [InlineKeyboardButton(text="🎨 Emoji sozlamalari", callback_data="admin:emojis", style="success")],
        [InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="admin:settings", style="success")],
    ])


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("🛠 Admin panel:", reply_markup=admin_menu_kb())


@router.callback_query(F.data == "admin:main")
async def admin_main(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    await callback.message.edit_text("🛠 Admin panel:", reply_markup=admin_menu_kb())
    await callback.answer()


# ---------- KATEGORIYA QO'SHISH ----------
@router.callback_query(F.data == "admin:add_cat")
async def add_cat_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AddCategory.name)
    await callback.message.edit_text(
        "Yangi kategoriya nomini yozing (masalan: Telegram Premium):"
    )
    await callback.answer()


@router.message(AddCategory.name)
async def add_cat_finish(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    db.add_category(message.text.strip())
    await state.clear()
    await message.answer(
        f"✅ «{message.text.strip()}» kategoriyasi qo'shildi.",
        reply_markup=admin_menu_kb()
    )


# ---------- KATEGORIYALARNI BOSHQARISH ----------
@router.callback_query(F.data == "admin:categories")
async def list_categories_admin(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    categories = db.get_categories()
    if not categories:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin:main")]
        ])
        await callback.message.edit_text("Kategoriyalar mavjud emas.", reply_markup=kb)
        await callback.answer()
        return

    buttons = [
        [InlineKeyboardButton(text=cat["name"], callback_data=f"admin:cat:{cat['id']}", style="success")]
        for cat in categories
    ]
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin:main")])
    await callback.message.edit_text(
        "Boshqarish uchun kategoriyani tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:cat:"))
async def manage_category(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    category_id = int(callback.data.split(":")[2])
    category = db.get_category(category_id)
    items = db.get_items_by_category(category_id)

    text = f"📂 {category['name']}\n\nXizmatlar:\n"
    if items:
        for it in items:
            text += f"• {it['name']} — {it['price']:,} so'm\n".replace(",", " ")
    else:
        text += "(hozircha yo'q)"

    buttons = [
        [InlineKeyboardButton(text="➕ Xizmat qo'shish", callback_data=f"admin:additem:{category_id}", style="primary")],
    ]
    for it in items:
        buttons.append([
            InlineKeyboardButton(text=f"✏️ {it['name']}", callback_data=f"admin:item:{it['id']}", style="success"),
            InlineKeyboardButton(text="🗑", callback_data=f"admin:delitem:{it['id']}:{category_id}", style="danger"),
        ])
    buttons.append([InlineKeyboardButton(text="✏️ Nomini o'zgartirish", callback_data=f"admin:renamecat:{category_id}", style="success")])
    buttons.append([InlineKeyboardButton(text="🗑 Kategoriyani o'chirish", callback_data=f"admin:delcat:{category_id}", style="danger")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin:categories")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:delcat:"))
async def delete_category_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    category_id = int(callback.data.split(":")[2])
    db.delete_category(category_id)
    await callback.answer("Kategoriya o'chirildi ✅", show_alert=True)
    await list_categories_admin(callback)


@router.callback_query(F.data.startswith("admin:renamecat:"))
async def rename_category_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    category_id = int(callback.data.split(":")[2])
    await state.update_data(category_id=category_id)
    await state.set_state(RenameCategory.new_name)
    await callback.message.edit_text("Kategoriyaning yangi nomini yozing:")
    await callback.answer()


@router.message(RenameCategory.new_name)
async def rename_category_finish(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    db.rename_category(data["category_id"], message.text.strip())
    await state.clear()
    await message.answer(
        f"✅ Kategoriya nomi «{message.text.strip()}» ga o'zgartirildi.",
        reply_markup=admin_menu_kb()
    )


# ---------- XIZMAT QO'SHISH ----------
@router.callback_query(F.data.startswith("admin:additem:"))
async def add_item_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    category_id = int(callback.data.split(":")[2])
    await state.update_data(category_id=category_id)
    await state.set_state(AddItem.name)
    await callback.message.edit_text(
        "Xizmat nomini yozing (masalan: Telegram Premium 1 oylik):"
    )
    await callback.answer()


@router.message(AddItem.name)
async def add_item_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(AddItem.price)
    await message.answer("Narxini kiriting (faqat raqam, so'mda). Masalan: 50000")


@router.message(AddItem.price)
async def add_item_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text.strip().isdigit():
        await message.answer("❗️ Iltimos, narxni faqat raqam bilan kiriting. Masalan: 50000")
        return
    await state.update_data(price=int(message.text.strip()))
    await state.set_state(AddItem.info)
    await message.answer(
        "Qo'shimcha izoh kiriting (masalan: yetkazib berish shartlari).\n"
        f"Agar kerak bo'lmasa, «-» deb yozing. {tge('exclaim', '‼️')}"
    )


@router.message(AddItem.info)
async def add_item_info(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    info = "" if message.text.strip() == "-" else message.text.strip()
    db.add_item(data["category_id"], data["name"], data["price"], info)
    await state.clear()
    await message.answer(
        f"✅ «{data['name']}» xizmati qo'shildi — {data['price']:,} so'm".replace(",", " "),
        reply_markup=admin_menu_kb()
    )


# ---------- XIZMATNI TAHRIRLASH / O'CHIRISH ----------
@router.callback_query(F.data.startswith("admin:item:"))
async def edit_item_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    item_id = int(callback.data.split(":")[2])
    item = db.get_item(item_id)
    top_status = "✅ Ha" if item["is_top"] else "❌ Yo'q"
    text = (
        f"📦 {item['name']}\n"
        f"💵 Narxi: {item['price']:,} so'm\n".replace(",", " ") +
        f"ℹ️ Izoh: {item['info'] or '-'}\n"
        f"🔥 Top taklif: {top_status}"
    )
    top_button_text = "🔥 Top'dan olib tashlash" if item["is_top"] else "🔥 Top taklifga qo'shish"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Narxni o'zgartirish", callback_data=f"admin:editprice:{item_id}", style="success")],
        [InlineKeyboardButton(text=top_button_text, callback_data=f"admin:toggletop:{item_id}", style="success")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"admin:cat:{item['category_id']}")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:toggletop:"))
async def toggle_top_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    item_id = int(callback.data.split(":")[2])
    new_state = db.toggle_item_top(item_id)
    await callback.answer(
        "🔥 Top taklifga qo'shildi ✅" if new_state else "Top taklifdan olib tashlandi",
        show_alert=True
    )
    await edit_item_menu(callback)


@router.callback_query(F.data.startswith("admin:delitem:"))
async def delete_item_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")
    item_id, category_id = int(parts[2]), int(parts[3])
    db.delete_item(item_id)
    await callback.answer("Xizmat o'chirildi ✅", show_alert=True)
    fake_cb_data = f"admin:cat:{category_id}"
    callback.data = fake_cb_data
    await manage_category(callback)


@router.callback_query(F.data.startswith("admin:editprice:"))
async def edit_price_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    item_id = int(callback.data.split(":")[2])
    await state.update_data(item_id=item_id)
    await state.set_state(EditPrice.new_price)
    await callback.message.edit_text("Yangi narxni kiriting (faqat raqam):")
    await callback.answer()


@router.message(EditPrice.new_price)
async def edit_price_finish(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text.strip().isdigit():
        await message.answer("❗️ Iltimos, faqat raqam kiriting.")
        return
    data = await state.get_data()
    db.update_item_price(data["item_id"], int(message.text.strip()))
    await state.clear()
    await message.answer("✅ Narx yangilandi.", reply_markup=admin_menu_kb())


# ---------- SOZLAMALAR ----------
@router.callback_query(F.data == "admin:settings")
async def settings_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    admin_username = db.get_setting("admin_username")
    channel_url = db.get_setting("channel_url")
    text = f"⚙️ Sozlamalar:\n\nAdmin username: {admin_username}\nKanal link: {channel_url}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Admin username", callback_data="admin:set_admin", style="success")],
        [InlineKeyboardButton(text="✏️ Kanal link", callback_data="admin:set_channel", style="success")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin:main")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "admin:set_admin")
async def set_admin_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(EditSettings.admin_username)
    await callback.message.edit_text("Yangi admin username kiriting (masalan: @username):")
    await callback.answer()


@router.message(EditSettings.admin_username)
async def set_admin_finish(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    db.set_setting("admin_username", message.text.strip())
    await state.clear()
    await message.answer("✅ Admin username yangilandi.", reply_markup=admin_menu_kb())


@router.callback_query(F.data == "admin:set_channel")
async def set_channel_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(EditSettings.channel_url)
    await callback.message.edit_text("Yangi kanal linkini kiriting (masalan: https://t.me/kanal):")
    await callback.answer()


@router.message(EditSettings.channel_url)
async def set_channel_finish(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    db.set_setting("channel_url", message.text.strip())
    await state.clear()
    await message.answer("✅ Kanal link yangilandi.", reply_markup=admin_menu_kb())


# ---------- PROMOKODLAR ----------
@router.callback_query(F.data == "admin:promos")
async def promos_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    promos = db.get_all_promocodes()
    text = "🎟 Promokodlar:\n\n"
    if promos:
        for p in promos:
            text += f"• {p['code']} — {p['discount']:,} so'm chegirma\n".replace(",", " ")
    else:
        text += "(hozircha yo'q)"

    buttons = [[InlineKeyboardButton(text="➕ Promokod qo'shish", callback_data="admin:addpromo", style="primary")]]
    for p in promos:
        buttons.append([InlineKeyboardButton(
            text=f"🗑 {p['code']} o'chirish", callback_data=f"admin:delpromo:{p['code']}", style="danger"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin:main")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


@router.callback_query(F.data == "admin:addpromo")
async def add_promo_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AddPromo.code)
    await callback.message.edit_text("Promokod matnini kiriting (masalan: SALOM):")
    await callback.answer()


@router.message(AddPromo.code)
async def add_promo_code(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(code=message.text.strip())
    await state.set_state(AddPromo.discount)
    await message.answer("Chegirma summasini kiriting (so'mda, faqat raqam). Masalan: 5000")


@router.message(AddPromo.discount)
async def add_promo_discount(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text.strip().isdigit():
        await message.answer("❗️ Iltimos, faqat raqam kiriting.")
        return
    data = await state.get_data()
    db.add_promocode(data["code"], int(message.text.strip()))
    await state.clear()
    await message.answer(
        f"✅ «{data['code'].upper()}» promokodi qo'shildi — {int(message.text.strip()):,} so'm chegirma".replace(",", " "),
        reply_markup=admin_menu_kb()
    )


@router.callback_query(F.data.startswith("admin:delpromo:"))
async def delete_promo_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    code = callback.data.split(":", 2)[2]
    db.delete_promocode(code)
    await callback.answer("Promokod o'chirildi ✅", show_alert=True)
    await promos_menu(callback)


# ---------- REKLAMA YUBORISH ----------
@router.callback_query(F.data == "admin:broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    user_count = db.get_user_count()
    await state.set_state(BroadcastState.waiting_content)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin:main")]
    ])
    await callback.message.edit_text(
        f"📢 Reklama xabarini yuboring (matn, rasm, video - har qanday turi bo'lishi mumkin).\n\n"
        f"Hozircha botdan {user_count} kishi foydalangan.",
        reply_markup=kb
    )
    await callback.answer()


@router.message(BroadcastState.waiting_content)
async def broadcast_received(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(chat_id=message.chat.id, message_id=message.message_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↪️ Forward qilib yuborish", callback_data="admin:bcast_forward", style="primary")],
        [InlineKeyboardButton(text="📋 Nusxa sifatida (forwardsiz)", callback_data="admin:bcast_copy", style="success")],
        [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin:main")],
    ])
    await message.answer("Qanday yuborilsin?", reply_markup=kb)


@router.callback_query(F.data.in_(["admin:bcast_forward", "admin:bcast_copy"]))
async def broadcast_send(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    data = await state.get_data()
    chat_id, message_id = data["chat_id"], data["message_id"]
    forward = callback.data == "admin:bcast_forward"
    await state.clear()

    await callback.message.edit_text("⏳ Yuborilmoqda, kuting...")
    await callback.answer()

    user_ids = db.get_all_user_ids()
    success, failed = 0, 0
    for uid in user_ids:
        try:
            if forward:
                await bot.forward_message(chat_id=uid, from_chat_id=chat_id, message_id=message_id)
            else:
                await bot.copy_message(chat_id=uid, from_chat_id=chat_id, message_id=message_id)
            success += 1
        except Exception:
            failed += 1

    await callback.message.edit_text(
        f"✅ Reklama yuborildi!\n\n"
        f"Muvaffaqiyatli: {success}\n"
        f"Yuborilmadi (bot bloklangan va h.k.): {failed}",
        reply_markup=admin_menu_kb()
    )


# ---------- EMOJI SOZLAMALARI ----------
EMOJI_LABELS = {
    "emoji_services": "Xizmatlar tugmasi",
    "emoji_contact": "Admin bilan aloqa tugmasi",
    "emoji_channel": "Biz kanali tugmasi",
    "emoji_top": "Top takliflar tugmasi",
    "emoji_order": "Buyurtma berish tugmasi",
    "emoji_back": "Orqaga tugmasi",
}


@router.callback_query(F.data == "admin:emojis")
async def emoji_settings_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    text = "🎨 Tugma emojilari:\n\n"
    buttons = []
    for key, label in EMOJI_LABELS.items():
        current = db.get_setting(key) or "-"
        text += f"{current} — {label}\n"
        buttons.append([InlineKeyboardButton(text=f"✏️ {label}", callback_data=f"admin:setemoji:{key}", style="success")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin:main")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:setemoji:"))
async def set_emoji_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    key = callback.data.split(":", 2)[2]
    await state.update_data(key=key)
    await state.set_state(EditEmoji.new_emoji)
    label = EMOJI_LABELS.get(key, key)
    await callback.message.edit_text(f"«{label}» uchun yangi emojini yuboring (masalan: 🟢):")
    await callback.answer()


@router.message(EditEmoji.new_emoji)
async def set_emoji_finish(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    db.set_setting(data["key"], message.text.strip())
    await state.clear()
    await message.answer("✅ Emoji yangilandi.", reply_markup=admin_menu_kb())


# ---------- STATISTIKA ----------
@router.callback_query(F.data == "admin:stats")
async def stats_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    user_count = db.get_user_count()
    order_count = db.get_order_count()
    total_revenue = db.get_total_revenue()

    text = (
        "📊 <b>Statistika</b>\n\n"
        f"👥 Jami foydalanuvchilar: {user_count}\n"
        f"🧾 Jami buyurtmalar: {order_count}\n"
        f"💵 Jami tushum: {total_revenue:,} so'm".replace(",", " ")
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin:main")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ---------- BALANS TO'LDIRISHNI TASDIQLASH/RAD ETISH ----------
@router.callback_query(F.data.startswith("topup_ok:"))
async def topup_approve(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    topup_id = int(callback.data.split(":")[1])
    topup = db.get_topup(topup_id)

    if not topup or topup["status"] != "pending":
        await callback.answer("Bu so'rov allaqachon ko'rib chiqilgan.", show_alert=True)
        return

    new_balance = db.add_balance(topup["user_id"], topup["amount"])
    db.set_topup_status(topup_id, "approved")

    await callback.message.edit_caption(
        caption=callback.message.caption + "\n\n✅ TASDIQLANDI",
        reply_markup=None
    )
    await callback.answer("Tasdiqlandi ✅")

    await bot.send_message(
        topup["user_id"],
        f"✅ Balansingiz {topup['amount']:,} so'mga to'ldirildi!\n\n".replace(",", " ") +
        f"💰 Joriy balans: {new_balance:,} so'm".replace(",", " ")
    )


@router.callback_query(F.data.startswith("topup_no:"))
async def topup_decline(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    topup_id = int(callback.data.split(":")[1])
    topup = db.get_topup(topup_id)

    if not topup or topup["status"] != "pending":
        await callback.answer("Bu so'rov allaqachon ko'rib chiqilgan.", show_alert=True)
        return

    db.set_topup_status(topup_id, "declined")

    await callback.message.edit_caption(
        caption=callback.message.caption + "\n\n❌ RAD ETILDI",
        reply_markup=None
    )
    await callback.answer("Rad etildi")

    await bot.send_message(topup["user_id"], "⚠️ To'lovingiz bekor qilindi.")


# ---------- FOYDALANUVCHILARNI BOSHQARISH ----------
@router.callback_query(F.data == "admin:users")
async def users_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    user_count = db.get_user_count()
    await state.set_state(FindUser.waiting_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin:main")]
    ])
    await callback.message.edit_text(
        f"👥 Jami foydalanuvchilar: {user_count}\n\n"
        "⭐ Kerakli foydalanuvchining ID raqamini kiriting:",
        reply_markup=kb
    )
    await callback.answer()


@router.message(FindUser.waiting_id)
async def users_find(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text.strip().isdigit():
        await message.answer("❗️ Iltimos, faqat ID raqamini kiriting.")
        return

    user_id = int(message.text.strip())
    user = db.get_user(user_id)
    await state.clear()

    if not user:
        await message.answer("❌ Bunday foydalanuvchi topilmadi.", reply_markup=admin_menu_kb())
        return

    await show_user_card(message, user_id)


async def show_user_card(message: Message, user_id: int):
    user = db.get_user(user_id)
    blocked_status = "🔴 Bloklangan" if user["blocked"] else "🟢 Faol"
    username_line = f"💬 Username: @{user['username']}" if user["username"] else "💬 Username: -"
    text = (
        "👤 <b>Foydalanuvchi topildi!</b>\n\n"
        f"🆔 ID: {user['user_id']}\n"
        f"📱 Telefon: {user['phone'] or '-'}\n"
        f"👤 Ism: {user['full_name'] or '-'}\n"
        f"{username_line}\n"
        f"💰 Balans: {user['balance']:,} so'm\n".replace(",", " ") +
        f"Holat: {blocked_status}"
    )
    block_text = "🔓 Blokdan chiqarish" if user["blocked"] else "🚫 Bloklash"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Pul qo'shish", callback_data=f"admin:addbal:{user_id}", style="success"),
            InlineKeyboardButton(text="➖ Pul ayirish", callback_data=f"admin:subbal:{user_id}", style="danger"),
        ],
        [InlineKeyboardButton(text=block_text, callback_data=f"admin:toggleblock:{user_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin:main")],
    ])
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("admin:toggleblock:"))
async def toggle_block_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split(":")[2])
    user = db.get_user(user_id)
    db.set_blocked(user_id, not user["blocked"])
    await callback.answer("Holat yangilandi ✅", show_alert=True)
    await show_user_card(callback.message, user_id)


@router.callback_query(F.data.startswith("admin:addbal:"))
async def add_balance_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split(":")[2])
    await state.update_data(user_id=user_id, mode="add")
    await state.set_state(AdjustBalance.amount)
    await callback.message.edit_text("Qo'shiladigan summani kiriting (so'mda):")
    await callback.answer()


@router.callback_query(F.data.startswith("admin:subbal:"))
async def sub_balance_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split(":")[2])
    await state.update_data(user_id=user_id, mode="subtract")
    await state.set_state(AdjustBalance.amount)
    await callback.message.edit_text("Ayiriladigan summani kiriting (so'mda):")
    await callback.answer()


@router.message(AdjustBalance.amount)
async def adjust_balance_finish(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    if not message.text.strip().isdigit():
        await message.answer("❗️ Iltimos, faqat raqam kiriting.")
        return

    data = await state.get_data()
    user_id, mode = data["user_id"], data["mode"]
    amount = int(message.text.strip())
    delta = amount if mode == "add" else -amount
    new_balance = db.add_balance(user_id, delta)
    await state.clear()

    await message.answer(
        f"✅ Balans yangilandi. Yangi balans: {new_balance:,} so'm".replace(",", " "),
        reply_markup=admin_menu_kb()
    )

    try:
        if mode == "add":
            await bot.send_message(user_id, f"💰 Balansingizga {amount:,} so'm qo'shildi.".replace(",", " "))
        else:
            await bot.send_message(user_id, f"💰 Balansingizdan {amount:,} so'm ayirildi.".replace(",", " "))
    except Exception:
        pass


# ---------- TO'LOV SOZLAMALARI ----------
@router.callback_query(F.data == "admin:payment_settings")
async def payment_settings_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    card_number = db.get_setting("payment_card_number")
    card_owner = db.get_setting("payment_card_owner")
    min_amount = db.get_setting("payment_min_amount")

    text = (
        "💳 <b>To'lov sozlamalari</b>\n\n"
        f"Karta raqami: {card_number}\n"
        f"Karta egasi: {card_owner}\n"
        f"Minimal summa: {min_amount} so'm"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Karta raqami", callback_data="admin:set_card_number")],
        [InlineKeyboardButton(text="✏️ Karta egasi", callback_data="admin:set_card_owner")],
        [InlineKeyboardButton(text="✏️ Minimal summa", callback_data="admin:set_min_amount")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin:main")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "admin:set_card_number")
async def set_card_number_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(PaymentSettings.card_number)
    await callback.message.edit_text("Yangi karta raqamini kiriting:")
    await callback.answer()


@router.message(PaymentSettings.card_number)
async def set_card_number_finish(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    db.set_setting("payment_card_number", message.text.strip())
    await state.clear()
    await message.answer("✅ Karta raqami yangilandi.", reply_markup=admin_menu_kb())


@router.callback_query(F.data == "admin:set_card_owner")
async def set_card_owner_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(PaymentSettings.card_owner)
    await callback.message.edit_text("Karta egasining F.I.SH kiriting:")
    await callback.answer()


@router.message(PaymentSettings.card_owner)
async def set_card_owner_finish(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    db.set_setting("payment_card_owner", message.text.strip())
    await state.clear()
    await message.answer("✅ Karta egasi yangilandi.", reply_markup=admin_menu_kb())


@router.callback_query(F.data == "admin:set_min_amount")
async def set_min_amount_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(PaymentSettings.min_amount)
    await callback.message.edit_text("Minimal to'ldirish summasini kiriting (so'mda):")
    await callback.answer()


@router.message(PaymentSettings.min_amount)
async def set_min_amount_finish(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text.strip().isdigit():
        await message.answer("❗️ Iltimos, faqat raqam kiriting.")
        return
    db.set_setting("payment_min_amount", message.text.strip())
    await state.clear()
    await message.answer("✅ Minimal summa yangilandi.", reply_markup=admin_menu_kb())


# ---------- NAKRUTKA (SMM) XIZMATLARI BOSHQARUVI ----------
@router.callback_query(F.data == "admin:smm")
async def smm_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    platforms = db.get_platforms()
    text = "📈 <b>Nakrutka xizmatlari</b>\n\n"
    if platforms:
        for p in platforms:
            services = db.get_smm_services_by_platform(p["id"])
            text += f"{p['emoji']} {p['name']} — {len(services)} ta xizmat\n"
    else:
        text += "(hozircha platforma qo'shilmagan)"

    buttons = [
        [InlineKeyboardButton(text="➕ Platforma qo'shish", callback_data="admin:add_platform", style="primary")],
        [InlineKeyboardButton(text="🔍 Panel xizmatlarini qidirish", callback_data="admin:search_panel", style="primary")],
    ]
    for p in platforms:
        buttons.append([InlineKeyboardButton(
            text=f"{p['emoji']} {p['name']}", callback_data=f"admin:platform:{p['id']}", style="success"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin:main")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


@router.callback_query(F.data == "admin:add_platform")
async def add_platform_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AddPlatform.name)
    await callback.message.edit_text("Platforma nomini kiriting (masalan: Telegram):")
    await callback.answer()


@router.message(AddPlatform.name)
async def add_platform_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(AddPlatform.emoji)
    await message.answer("Endi platforma uchun emoji yuboring (masalan: ✈️):")


@router.message(AddPlatform.emoji)
async def add_platform_emoji(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    db.add_platform(data["name"], message.text.strip())
    await state.clear()
    await message.answer(f"✅ «{data['name']}» platformasi qo'shildi.", reply_markup=admin_menu_kb())


@router.callback_query(F.data.startswith("admin:platform:"))
async def manage_platform(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    platform_id = int(callback.data.split(":")[2])
    platform = db.get_platform(platform_id)
    services = db.get_smm_services_by_platform(platform_id)

    text = f"{platform['emoji']} <b>{platform['name']}</b>\n\nXizmatlar:\n"
    if services:
        for s in services:
            text += f"• {s['name']} — {s['price_per_1000']:,} so'm/1000\n".replace(",", " ")
    else:
        text += "(hozircha yo'q)"

    buttons = [
        [InlineKeyboardButton(text="➕ Xizmat qo'shish", callback_data=f"admin:add_smm_service:{platform_id}", style="primary")],
    ]
    for s in services:
        buttons.append([InlineKeyboardButton(
            text=f"🗑 {s['name']}", callback_data=f"admin:del_smm_service:{s['id']}:{platform_id}", style="danger"
        )])
    buttons.append([InlineKeyboardButton(text="🗑 Platformani o'chirish", callback_data=f"admin:del_platform:{platform_id}", style="danger")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin:smm")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:del_platform:"))
async def del_platform_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    platform_id = int(callback.data.split(":")[2])
    db.delete_platform(platform_id)
    await callback.answer("Platforma o'chirildi ✅", show_alert=True)
    await smm_menu(callback)


@router.callback_query(F.data.startswith("admin:del_smm_service:"))
async def del_smm_service_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")
    service_id, platform_id = int(parts[2]), int(parts[3])
    db.delete_smm_service(service_id)
    await callback.answer("Xizmat o'chirildi ✅", show_alert=True)
    await manage_platform(callback)


# ---------- 1XPANEL'DAN XIZMAT QIDIRISH ----------
@router.callback_query(F.data == "admin:search_panel")
async def search_panel_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(SearchPanelServices.keyword)
    await callback.message.edit_text(
        "🔍 Qidiruv so'zini kiriting (masalan: instagram followers, telegram members):"
    )
    await callback.answer()


@router.message(SearchPanelServices.keyword)
async def search_panel_result(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    keyword = message.text.strip().lower()

    await message.answer("⏳ Qidirilmoqda...")
    result = smm_api.get_services()

    if not isinstance(result, list):
        error = result.get("error") if isinstance(result, dict) else "Noma'lum xatolik"
        await message.answer(f"❌ Panel bilan bog'lanishda xatolik: {error}")
        return

    matches = [s for s in result if keyword in s.get("name", "").lower()][:15]

    if not matches:
        await message.answer("Hech narsa topilmadi. Boshqa so'z bilan urinib ko'ring.")
        return

    text = "🔍 Topilgan xizmatlar (birinchi 15 tasi):\n\n"
    for s in matches:
        text += (
            f"🆔 ID: {s.get('service')}\n"
            f"📦 {s.get('name')}\n"
            f"💵 Narx (panelda, $ yoki boshqa valyutada): {s.get('rate')} / 1000\n"
            f"🔢 Min: {s.get('min')} — Max: {s.get('max')}\n\n"
        )
    text += "Kerakli xizmatning ID raqamini «➕ Xizmat qo'shish» bosganda kiritasiz."

    await message.answer(text, reply_markup=admin_menu_kb())


# ---------- XIZMAT QO'SHISH (SMM) ----------
@router.callback_query(F.data.startswith("admin:add_smm_service:"))
async def add_smm_service_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    platform_id = int(callback.data.split(":")[2])
    await state.update_data(platform_id=platform_id)
    await state.set_state(AddSmmService.panel_service_id)
    await callback.message.edit_text(
        "Panel xizmat ID raqamini kiriting (avval «🔍 Panel xizmatlarini qidirish» orqali toping):"
    )
    await callback.answer()


@router.message(AddSmmService.panel_service_id)
async def add_smm_service_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text.strip().isdigit():
        await message.answer("❗️ Iltimos, faqat raqam kiriting.")
        return

    panel_id = int(message.text.strip())
    await message.answer("⏳ Xizmat ma'lumoti tekshirilmoqda...")

    result = smm_api.get_services()
    if not isinstance(result, list):
        error = result.get("error") if isinstance(result, dict) else "Noma'lum xatolik"
        await state.clear()
        await message.answer(f"❌ Panel bilan bog'lanishda xatolik: {error}", reply_markup=admin_menu_kb())
        return

    service_info = next((s for s in result if str(s.get("service")) == str(panel_id)), None)
    if not service_info:
        await message.answer(
            "❌ Bunday ID raqamli xizmat panelda topilmadi. Qaytadan kiriting, "
            "yoki avval «🔍 Panel xizmatlarini qidirish» orqali to'g'ri ID'ni toping:"
        )
        return

    # xpanel qaytargan ma'lumotlarni skrindagi uslubda ko'rsatamiz
    name = service_info.get("name", "-")
    rate = service_info.get("rate", "-")
    min_qty = service_info.get("min", "-")
    max_qty = service_info.get("max", "-")
    avg_time = service_info.get("average_time") or service_info.get("time") or service_info.get("eta")

    text = (
        f"📦 {name}\n\n"
        f"🔑 Xizmat IDsi: {panel_id}\n"
        f"📊 Narxi (1000x): {rate}\n"
    )
    if avg_time:
        text += f"⏰ Bajarilish vaqti: {avg_time}\n"
    text += (
        f"\n🔽 Minimal buyurtma: {min_qty} ta\n"
        f"🔼 Maksimal buyurtma: {max_qty} ta"
    )

    await state.update_data(panel_service_id=panel_id, panel_name=name)
    await state.set_state(AddSmmService.confirm_info)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Qo'shish", callback_data="admin:confirm_smm_add", style="success")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin:main", style="danger")],
    ])
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "admin:confirm_smm_add", AddSmmService.confirm_info)
async def confirm_smm_add(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    data = await state.get_data()
    suggested_name = data.get("panel_name", "")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha, shu nom qolsin", callback_data="admin:keep_panel_name", style="success")],
        [InlineKeyboardButton(text="✏️ Yo'q, o'zim yozaman", callback_data="admin:type_own_name", style="primary")],
    ])
    await callback.message.edit_text(
        f"📦 Xpanel'dagi nomi: <b>{suggested_name}</b>\n\n"
        "Shu nom mijozlarga shu holicha ko'rsatilsinmi?",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data == "admin:keep_panel_name", AddSmmService.confirm_info)
async def keep_panel_name(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    data = await state.get_data()
    await state.update_data(name=data.get("panel_name", ""))
    await state.set_state(AddSmmService.price)
    await callback.message.edit_text("1000 dona uchun sotish narxini kiriting (so'mda):")
    await callback.answer()


@router.callback_query(F.data == "admin:type_own_name", AddSmmService.confirm_info)
async def type_own_name(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AddSmmService.name)
    await callback.message.edit_text("Xizmat nomini kiriting (mijozlarga shu nom ko'rinadi):")
    await callback.answer()


@router.message(AddSmmService.name)
async def add_smm_service_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(AddSmmService.price)
    await message.answer("1000 dona uchun sotish narxini kiriting (so'mda):")


@router.message(AddSmmService.price)
async def add_smm_service_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text.strip().isdigit():
        await message.answer("❗️ Iltimos, faqat raqam kiriting.")
        return
    await state.update_data(price=int(message.text.strip()))
    await state.set_state(AddSmmService.min_qty)
    await message.answer("Minimal miqdorni kiriting:")


@router.message(AddSmmService.min_qty)
async def add_smm_service_min(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text.strip().isdigit():
        await message.answer("❗️ Iltimos, faqat raqam kiriting.")
        return
    await state.update_data(min_qty=int(message.text.strip()))
    await state.set_state(AddSmmService.max_qty)
    await message.answer("Maksimal miqdorni kiriting:")


@router.message(AddSmmService.max_qty)
async def add_smm_service_max(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text.strip().isdigit():
        await message.answer("❗️ Iltimos, faqat raqam kiriting.")
        return

    data = await state.get_data()
    db.add_smm_service(
        data["platform_id"], data["panel_service_id"], data["name"],
        data["price"], data["min_qty"], int(message.text.strip())
    )
    await state.clear()
    await message.answer(f"✅ «{data['name']}» xizmati qo'shildi.", reply_markup=admin_menu_kb())


# ---------- MAJBURIY OBUNA SOZLAMALARI ----------
@router.callback_query(F.data == "admin:required_channel")
async def required_channel_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    enabled = db.get_setting("require_channel_enabled") == "1"
    username = db.get_setting("require_channel_username") or "-"
    url = db.get_setting("require_channel_url") or "-"

    status_text = "✅ Yoqilgan" if enabled else "❌ O'chirilgan"
    toggle_text = "🔴 O'chirish" if enabled else "🟢 Yoqish"

    text = (
        "🔒 <b>Majburiy obuna</b>\n\n"
        f"Holati: {status_text}\n"
        f"Kanal username: {username}\n"
        f"Kanal link: {url}\n\n"
        "⚠️ Yoqishdan oldin botni o'sha kanalga <b>admin</b> qilib qo'yganingizga ishonch hosil qiling, "
        "aks holda obunani tekshira olmaydi."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data="admin:toggle_required_channel", style="danger" if enabled else "success")],
        [InlineKeyboardButton(text="✏️ Kanal username", callback_data="admin:set_req_channel_username")],
        [InlineKeyboardButton(text="✏️ Kanal link", callback_data="admin:set_req_channel_url")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin:main")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "admin:toggle_required_channel")
async def toggle_required_channel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    enabled = db.get_setting("require_channel_enabled") == "1"
    if not enabled and not db.get_setting("require_channel_username"):
        await callback.answer("❗️ Avval kanal username'ni kiriting.", show_alert=True)
        return
    db.set_setting("require_channel_enabled", "0" if enabled else "1")
    await callback.answer("Holat yangilandi ✅")
    await required_channel_menu(callback)


@router.callback_query(F.data == "admin:set_req_channel_username")
async def set_req_channel_username_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(RequiredChannel.username)
    await callback.message.edit_text(
        "Kanal username'ni kiriting (masalan: @mychannel):"
    )
    await callback.answer()


@router.message(RequiredChannel.username)
async def set_req_channel_username_finish(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    db.set_setting("require_channel_username", message.text.strip())
    await state.clear()
    await message.answer("✅ Kanal username saqlandi.", reply_markup=admin_menu_kb())


@router.callback_query(F.data == "admin:set_req_channel_url")
async def set_req_channel_url_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(RequiredChannel.url)
    await callback.message.edit_text(
        "Kanalga o'tish uchun havolani kiriting (masalan: https://t.me/mychannel):"
    )
    await callback.answer()


@router.message(RequiredChannel.url)
async def set_req_channel_url_finish(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    db.set_setting("require_channel_url", message.text.strip())
    await state.clear()
    await message.answer("✅ Kanal link saqlandi.", reply_markup=admin_menu_kb())
