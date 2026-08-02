# handlers_admin.py
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
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


# ---------- ADMIN ASOSIY MENYU ----------
def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kategoriya qo'shish", callback_data="admin:add_cat", style="primary")],
        [InlineKeyboardButton(text="📂 Kategoriyalarni boshqarish", callback_data="admin:categories", style="success")],
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
