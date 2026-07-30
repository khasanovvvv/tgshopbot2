# handlers_admin.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from config import ADMIN_ID

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


class EditSettings(StatesGroup):
    admin_username = State()
    channel_url = State()


# ---------- ADMIN ASOSIY MENYU ----------
def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kategoriya qo'shish", callback_data="admin:add_cat")],
        [InlineKeyboardButton(text="📂 Kategoriyalarni boshqarish", callback_data="admin:categories")],
        [InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="admin:settings")],
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
        [InlineKeyboardButton(text=cat["name"], callback_data=f"admin:cat:{cat['id']}")]
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
        [InlineKeyboardButton(text="➕ Xizmat qo'shish", callback_data=f"admin:additem:{category_id}")],
    ]
    for it in items:
        buttons.append([
            InlineKeyboardButton(text=f"✏️ {it['name']}", callback_data=f"admin:item:{it['id']}"),
            InlineKeyboardButton(text="🗑", callback_data=f"admin:delitem:{it['id']}:{category_id}"),
        ])
    buttons.append([InlineKeyboardButton(text="🗑 Kategoriyani o'chirish", callback_data=f"admin:delcat:{category_id}")])
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
        "Agar kerak bo'lmasa, «-» deb yozing."
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
    text = (
        f"📦 {item['name']}\n"
        f"💵 Narxi: {item['price']:,} so'm\n".replace(",", " ") +
        f"ℹ️ Izoh: {item['info'] or '-'}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Narxni o'zgartirish", callback_data=f"admin:editprice:{item_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"admin:cat:{item['category_id']}")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


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
        [InlineKeyboardButton(text="✏️ Admin username", callback_data="admin:set_admin")],
        [InlineKeyboardButton(text="✏️ Kanal link", callback_data="admin:set_channel")],
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
