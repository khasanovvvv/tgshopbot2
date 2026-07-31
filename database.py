# database.py
# Endi ma'lumotlar Supabase (bepul, doimiy PostgreSQL) da saqlanadi.
# Render qayta ishga tushsa ham, ma'lumotlar YO'QOLMAYDI.
import os
import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "")


def get_conn():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn


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

    conn.commit()
    cur.close()
    conn.close()


# ---------- FOYDALANUVCHILAR (reklama uchun) ----------
def add_user(user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
    conn.commit()
    cur.close()
    conn.close()


def get_all_user_ids():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [row["user_id"] for row in rows]


def get_user_count() -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM users")
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row["c"]


# ---------- BUYURTMALAR (statistika uchun) ----------
def log_order(item_id: int, user_id: int, price: int, promo_code: str = None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO orders (item_id, user_id, price, promo_code) VALUES (%s, %s, %s, %s)",
        (item_id, user_id, price, promo_code)
    )
    conn.commit()
    cur.close()
    conn.close()


def get_order_count() -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM orders")
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row["c"]


def get_total_revenue() -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(SUM(price), 0) AS s FROM orders")
    row = cur.fetchone()
    cur.close()
    conn.close()
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
    conn.close()


def get_promocode(code: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM promocodes WHERE code = %s AND active = 1", (code.upper(),))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def get_all_promocodes():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM promocodes ORDER BY code")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def delete_promocode(code: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM promocodes WHERE code = %s", (code.upper(),))
    conn.commit()
    cur.close()
    conn.close()


# ---------- SETTINGS ----------
def get_setting(key: str) -> str:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = %s", (key,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row["value"] if row else ""


def set_setting(key: str, value: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE settings SET value = %s WHERE key = %s", (value, key))
    conn.commit()
    cur.close()
    conn.close()


# ---------- CATEGORIES ----------
def add_category(name: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO categories (name) VALUES (%s) RETURNING id", (name,))
    new_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()
    return new_id


def get_categories():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM categories ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_category(category_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM categories WHERE id = %s", (category_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def delete_category(category_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM items WHERE category_id = %s", (category_id,))
    cur.execute("DELETE FROM categories WHERE id = %s", (category_id,))
    conn.commit()
    cur.close()
    conn.close()


def rename_category(category_id: int, new_name: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE categories SET name = %s WHERE id = %s", (new_name, category_id))
    conn.commit()
    cur.close()
    conn.close()


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
    conn.close()
    return new_id


def get_items_by_category(category_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM items WHERE category_id = %s ORDER BY id", (category_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_item(item_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM items WHERE id = %s", (item_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def update_item_price(item_id: int, new_price: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE items SET price = %s WHERE id = %s", (new_price, item_id))
    conn.commit()
    cur.close()
    conn.close()


def update_item_info(item_id: int, new_info: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE items SET info = %s WHERE id = %s", (new_info, item_id))
    conn.commit()
    cur.close()
    conn.close()


def update_item_name(item_id: int, new_name: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE items SET name = %s WHERE id = %s", (new_name, item_id))
    conn.commit()
    cur.close()
    conn.close()


def delete_item(item_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM items WHERE id = %s", (item_id,))
    conn.commit()
    cur.close()
    conn.close()


def get_top_items():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM items WHERE is_top = 1 ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
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
    conn.close()
    return bool(new_value)
