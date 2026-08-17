# database.py
# Endi ma'lumotlar Supabase (bepul, doimiy PostgreSQL) da saqlanadi.
# Render qayta ishga tushsa ham, ma'lumotlar YO'QOLMAYDI.
#
# ULANISHLAR HOVUZI (connection pool): har safar yangi tarmoq ulanishi
# o'rnatish o'rniga, bir nechta ulanish oldindan ochib qo'yiladi va qayta
# ishlatiladi. Bu botni SEZILARLI tezlashtiradi (ayniqsa Supabase serveri
# uzoqroq mintaqada bo'lsa).
import os
import psycopg2
import psycopg2.extras
from psycopg2 import pool as pg_pool

DATABASE_URL = os.environ.get("DATABASE_URL", "")

_pool = pg_pool.SimpleConnectionPool(1, 10, DATABASE_URL)


def get_conn():
    conn = _pool.getconn()
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    return conn


def release(conn):
    _pool.putconn(conn)


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id SERIAL PRIMARY KEY,
            category_id INTEGER NOT NULL REFERENCES categories(id),
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            info TEXT DEFAULT '',
            is_top INTEGER DEFAULT 0
        )
    """)
    cur.execute("ALTER TABLE items ADD COLUMN IF NOT EXISTS is_top INTEGER DEFAULT 0")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cur.execute(
        "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING",
        ("admin_username", "@your_admin")
    )
    cur.execute(
        "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING",
        ("require_channel_enabled", "0")
    )
    cur.execute(
        "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING",
        ("require_channel_username", "")
    )
    cur.execute(
        "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING",
        ("require_channel_url", "")
    )
    cur.execute(
        "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING",
        ("dollar_rate", "12700")
    )
    cur.execute(
        "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING",
        ("smm_default_markup", "100")
    )
    cur.execute(
        "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING",
        ("channel_url", "https://t.me/your_channel")
    )
    default_emojis = {
        "emoji_services": "🛍",
        "emoji_contact": "👨‍💻",
        "emoji_channel": "📢",
        "emoji_top": "🔥",
        "emoji_order": "✅",
        "emoji_back": "🔙",
    }
    for key, value in default_emojis.items():
        cur.execute(
            "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING",
            (key, value)
        )

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY
        )
    """)
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name TEXT")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS balance INTEGER DEFAULT 0")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS blocked INTEGER DEFAULT 0")

    cur.execute(
        "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING",
        ("payment_card_number", "0000 0000 0000 0000")
    )
    cur.execute(
        "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING",
        ("payment_min_amount", "1000")
    )
    cur.execute(
        "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING",
        ("payment_card_owner", "F.I.SH")
    )

    cur.execute("""
        CREATE TABLE IF NOT EXISTS topups (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            amount INTEGER,
            receipt_file_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS promocodes (
            code TEXT PRIMARY KEY,
            discount INTEGER NOT NULL,
            active INTEGER DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            item_id INTEGER,
            user_id BIGINT,
            price INTEGER,
            promo_code TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS order_type TEXT DEFAULT 'item'")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'yangi'")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS item_name TEXT")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS link TEXT")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS quantity INTEGER")
    cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS panel_order_id INTEGER")

    # ---- NAKRUTKA (SMM) XIZMATLARI ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS smm_platforms (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            emoji TEXT DEFAULT '📱',
            sort_order INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS smm_categories (
            id SERIAL PRIMARY KEY,
            platform_id INTEGER NOT NULL REFERENCES smm_platforms(id),
            name TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS smm_services (
            id SERIAL PRIMARY KEY,
            category_id INTEGER REFERENCES smm_categories(id),
            panel_service_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            price_per_1000 INTEGER NOT NULL,
            min_qty INTEGER NOT NULL,
            max_qty INTEGER NOT NULL,
            average_time TEXT DEFAULT ''
        )
    """)
    cur.execute("ALTER TABLE smm_services ADD COLUMN IF NOT EXISTS average_time TEXT DEFAULT ''")
    cur.execute("ALTER TABLE smm_services ADD COLUMN IF NOT EXISTS category_id INTEGER REFERENCES smm_categories(id)")
    # eski bazalarda "platform_id" ustuni NOT NULL bo'lib qolgan bo'lishi mumkin -
    # endi xizmatlar category_id orqali bog'lanadi, shu sababli bu cheklovni olib tashlaymiz
    try:
        cur.execute("ALTER TABLE smm_services ALTER COLUMN platform_id DROP NOT NULL")
    except Exception:
        conn.rollback()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS smm_orders (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            service_id INTEGER,
            link TEXT,
            quantity INTEGER,
            price INTEGER,
            panel_order_id INTEGER,
            status TEXT DEFAULT 'yuborildi',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    conn.commit()
    cur.close()
    release(conn)


# ---------- FOYDALANUVCHILAR (reklama uchun) ----------
def add_user(user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
    conn.commit()
    cur.close()
    release(conn)


def save_user_info(user_id: int, phone: str = None, full_name: str = None, username: str = None):
    conn = get_conn()
    cur = conn.cursor()
    if phone is not None:
        cur.execute("UPDATE users SET phone = %s WHERE user_id = %s", (phone, user_id))
    if full_name is not None:
        cur.execute("UPDATE users SET full_name = %s WHERE user_id = %s", (full_name, user_id))
    if username is not None:
        cur.execute("UPDATE users SET username = %s WHERE user_id = %s", (username, user_id))
    conn.commit()
    cur.close()
    release(conn)


def get_user(user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    release(conn)
    return row


def has_phone(user_id: int) -> bool:
    user = get_user(user_id)
    return bool(user and user["phone"])


def is_blocked(user_id: int) -> bool:
    user = get_user(user_id)
    return bool(user and user["blocked"])


def set_blocked(user_id: int, blocked: bool):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET blocked = %s WHERE user_id = %s", (1 if blocked else 0, user_id))
    conn.commit()
    cur.close()
    release(conn)


def get_all_user_ids():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    rows = cur.fetchall()
    cur.close()
    release(conn)
    return [row["user_id"] for row in rows]


def get_user_count() -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM users")
    row = cur.fetchone()
    cur.close()
    release(conn)
    return row["c"]


# ---------- BALANS ----------
def get_balance(user_id: int) -> int:
    user = get_user(user_id)
    return user["balance"] if user else 0


def add_balance(user_id: int, amount: int) -> int:
    """Balansga qo'shadi (manfiy son bo'lsa ayiradi). Yangi balansni qaytaradi."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET balance = GREATEST(0, balance + %s) WHERE user_id = %s RETURNING balance",
        (amount, user_id)
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    release(conn)
    return row["balance"] if row else 0


# ---------- BALANS TO'LDIRISH (TOPUP) ----------
def create_topup(user_id: int, amount: int, receipt_file_id: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO topups (user_id, amount, receipt_file_id) VALUES (%s, %s, %s) RETURNING id",
        (user_id, amount, receipt_file_id)
    )
    new_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    release(conn)
    return new_id


def get_topup(topup_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM topups WHERE id = %s", (topup_id,))
    row = cur.fetchone()
    cur.close()
    release(conn)
    return row


def set_topup_status(topup_id: int, status: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE topups SET status = %s WHERE id = %s", (status, topup_id))
    conn.commit()
    cur.close()
    release(conn)


# ---------- BUYURTMALAR (statistika uchun) ----------
def log_order(item_id: int, user_id: int, price: int, promo_code: str = None,
              order_type: str = "item", item_name: str = None,
              link: str = None, quantity: int = None, panel_order_id: int = None) -> int:
    """Buyurtmani saqlaydi va uning ketma-ket raqamini (id) qaytaradi."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO orders
           (item_id, user_id, price, promo_code, order_type, item_name, link, quantity, panel_order_id, status)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'yangi') RETURNING id""",
        (item_id, user_id, price, promo_code, order_type, item_name, link, quantity, panel_order_id)
    )
    new_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    release(conn)
    return new_id


def get_order(order_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
    row = cur.fetchone()
    cur.close()
    release(conn)
    return row


def get_user_orders(user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE user_id = %s ORDER BY id DESC", (user_id,))
    rows = cur.fetchall()
    cur.close()
    release(conn)
    return rows


def set_order_status(order_id: int, status: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status = %s WHERE id = %s", (status, order_id))
    conn.commit()
    cur.close()
    release(conn)


def get_order_count() -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM orders WHERE status != 'bekor qilindi'")
    row = cur.fetchone()
    cur.close()
    release(conn)
    return row["c"]


def get_total_revenue() -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(SUM(price), 0) AS s FROM orders WHERE status != 'bekor qilindi'")
    row = cur.fetchone()
    cur.close()
    release(conn)
    return row["s"]


# ---------- PROMOKODLAR ----------
def add_promocode(code: str, discount: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO promocodes (code, discount, active) VALUES (%s, %s, 1)
           ON CONFLICT (code) DO UPDATE SET discount = EXCLUDED.discount, active = 1""",
        (code.upper(), discount)
    )
    conn.commit()
    cur.close()
    release(conn)


def get_promocode(code: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM promocodes WHERE code = %s AND active = 1", (code.upper(),))
    row = cur.fetchone()
    cur.close()
    release(conn)
    return row


def get_all_promocodes():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM promocodes ORDER BY code")
    rows = cur.fetchall()
    cur.close()
    release(conn)
    return rows


def delete_promocode(code: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM promocodes WHERE code = %s", (code.upper(),))
    conn.commit()
    cur.close()
    release(conn)


# ---------- SETTINGS ----------
def get_setting(key: str) -> str:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = %s", (key,))
    row = cur.fetchone()
    cur.close()
    release(conn)
    return row["value"] if row else ""


def set_setting(key: str, value: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE settings SET value = %s WHERE key = %s", (value, key))
    conn.commit()
    cur.close()
    release(conn)


# ---------- CATEGORIES ----------
def add_category(name: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO categories (name) VALUES (%s) RETURNING id", (name,))
    new_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    release(conn)
    return new_id


def get_categories():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM categories ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    release(conn)
    return rows


def get_category(category_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM categories WHERE id = %s", (category_id,))
    row = cur.fetchone()
    cur.close()
    release(conn)
    return row


def delete_category(category_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM items WHERE category_id = %s", (category_id,))
    cur.execute("DELETE FROM categories WHERE id = %s", (category_id,))
    conn.commit()
    cur.close()
    release(conn)


def rename_category(category_id: int, new_name: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE categories SET name = %s WHERE id = %s", (new_name, category_id))
    conn.commit()
    cur.close()
    release(conn)


# ---------- ITEMS ----------
def add_item(category_id: int, name: str, price: int, info: str = "") -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO items (category_id, name, price, info) VALUES (%s, %s, %s, %s) RETURNING id",
        (category_id, name, price, info)
    )
    new_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    release(conn)
    return new_id


def get_items_by_category(category_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM items WHERE category_id = %s ORDER BY id", (category_id,))
    rows = cur.fetchall()
    cur.close()
    release(conn)
    return rows


def get_item(item_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM items WHERE id = %s", (item_id,))
    row = cur.fetchone()
    cur.close()
    release(conn)
    return row


def update_item_price(item_id: int, new_price: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE items SET price = %s WHERE id = %s", (new_price, item_id))
    conn.commit()
    cur.close()
    release(conn)


def update_item_info(item_id: int, new_info: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE items SET info = %s WHERE id = %s", (new_info, item_id))
    conn.commit()
    cur.close()
    release(conn)


def update_item_name(item_id: int, new_name: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE items SET name = %s WHERE id = %s", (new_name, item_id))
    conn.commit()
    cur.close()
    release(conn)


def delete_item(item_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM items WHERE id = %s", (item_id,))
    conn.commit()
    cur.close()
    release(conn)


def get_top_items():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM items WHERE is_top = 1 ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    release(conn)
    return rows


def toggle_item_top(item_id: int) -> bool:
    """Xizmatning 'top' holatini teskarisiga o'zgartiradi. Yangi holatni qaytaradi."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT is_top FROM items WHERE id = %s", (item_id,))
    row = cur.fetchone()
    new_value = 0 if row["is_top"] else 1
    cur.execute("UPDATE items SET is_top = %s WHERE id = %s", (new_value, item_id))
    conn.commit()
    cur.close()
    release(conn)
    return bool(new_value)


# ---------- SMM PLATFORMALAR ----------
def add_platform(name: str, emoji: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM smm_platforms"
    )
    next_order = cur.fetchone()["n"]
    cur.execute(
        "INSERT INTO smm_platforms (name, emoji, sort_order) VALUES (%s, %s, %s) RETURNING id",
        (name, emoji, next_order)
    )
    new_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    release(conn)
    return new_id


def get_platforms():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM smm_platforms ORDER BY sort_order")
    rows = cur.fetchall()
    cur.close()
    release(conn)
    return rows


def get_platform(platform_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM smm_platforms WHERE id = %s", (platform_id,))
    row = cur.fetchone()
    cur.close()
    release(conn)
    return row


def delete_platform(platform_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM smm_categories WHERE platform_id = %s", (platform_id,))
    category_ids = [row["id"] for row in cur.fetchall()]
    for cat_id in category_ids:
        cur.execute("DELETE FROM smm_services WHERE category_id = %s", (cat_id,))
    cur.execute("DELETE FROM smm_categories WHERE platform_id = %s", (platform_id,))
    cur.execute("DELETE FROM smm_platforms WHERE id = %s", (platform_id,))
    conn.commit()
    cur.close()
    release(conn)


# ---------- SMM KATEGORIYALAR (platforma ichidagi bo'limlar) ----------
def add_smm_category(platform_id: int, name: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM smm_categories WHERE platform_id = %s",
        (platform_id,)
    )
    next_order = cur.fetchone()["n"]
    cur.execute(
        "INSERT INTO smm_categories (platform_id, name, sort_order) VALUES (%s, %s, %s) RETURNING id",
        (platform_id, name, next_order)
    )
    new_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    release(conn)
    return new_id


def get_smm_categories(platform_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM smm_categories WHERE platform_id = %s ORDER BY sort_order", (platform_id,))
    rows = cur.fetchall()
    cur.close()
    release(conn)
    return rows


def get_smm_category(category_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM smm_categories WHERE id = %s", (category_id,))
    row = cur.fetchone()
    cur.close()
    release(conn)
    return row


def delete_smm_category(category_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM smm_services WHERE category_id = %s", (category_id,))
    cur.execute("DELETE FROM smm_categories WHERE id = %s", (category_id,))
    conn.commit()
    cur.close()
    release(conn)


# ---------- SMM XIZMATLAR ----------
def add_smm_service(category_id: int, panel_service_id: int, name: str,
                     price_per_1000: int, min_qty: int, max_qty: int, average_time: str = "") -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO smm_services
           (category_id, panel_service_id, name, price_per_1000, min_qty, max_qty, average_time)
           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (category_id, panel_service_id, name, price_per_1000, min_qty, max_qty, average_time)
    )
    new_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    release(conn)
    return new_id


def get_smm_services_by_category(category_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM smm_services WHERE category_id = %s ORDER BY id", (category_id,))
    rows = cur.fetchall()
    cur.close()
    release(conn)
    return rows


def get_smm_service(service_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM smm_services WHERE id = %s", (service_id,))
    row = cur.fetchone()
    cur.close()
    release(conn)
    return row


def delete_smm_service(service_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM smm_services WHERE id = %s", (service_id,))
    conn.commit()
    cur.close()
    release(conn)


# ---------- SMM BUYURTMALAR ----------
def create_smm_order(user_id: int, service_id: int, link: str, quantity: int,
                      price: int, panel_order_id: int) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO smm_orders (user_id, service_id, link, quantity, price, panel_order_id)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
        (user_id, service_id, link, quantity, price, panel_order_id)
    )
    new_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    release(conn)
    return new_id
